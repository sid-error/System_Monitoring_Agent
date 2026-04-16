import streamlit as st
import asyncio
import os
import sys

# Windows compatibility for asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from google.genai import types
import json
import re

def parse_json_blocks(text: str):
    """Extracts JSON blocks from the agent's response."""
    components = []
    pattern = re.compile(r'```json\s*(\{.*?\})\s*```|^\s*(\{.*?\})\s*$', re.DOTALL | re.MULTILINE)
    
    last_end = 0
    matches = list(pattern.finditer(text))
    
    if not matches:
        return [{"type": "text", "content": text}]

    for match in matches:
        plain = text[last_end:match.start()].strip()
        if plain:
            components.append({"type": "text", "content": plain})
            
        json_str = next((g for g in match.groups() if g is not None), "").strip()
        last_end = match.end()
        
        try:
            struct = json.loads(json_str)
            if isinstance(struct, dict) and (struct.get("type") == "table_and_chart" or "chart_type" in struct):
                components.append(struct)
            else:
                components.append({"type": "text", "content": match.group(0)})
        except:
            components.append({"type": "text", "content": match.group(0)})
            
    rem = text[last_end:].strip()
    if rem:
        components.append({"type": "text", "content": rem})
    return components

def render_content(content):
    components = parse_json_blocks(content)
    for comp in components:
        if comp["type"] == "text":
            st.markdown(comp["content"])
        else:
            if "data" in comp:
                st.dataframe(comp["data"], use_container_width=True)
                
                chart_type = comp.get("chart_type")
                x = comp.get("x_axis")
                y = comp.get("y_axis")
                
                if chart_type == "bar" and x and y:
                    st.bar_chart(comp["data"], x=x, y=y)
                elif chart_type == "pie" and x and y:
                    try:
                        import altair as alt
                        import pandas as pd
                        df = pd.DataFrame(comp["data"])
                        chart = alt.Chart(df).mark_arc().encode(
                            theta=alt.Theta(field=y, type="quantitative"),
                            color=alt.Color(field=x, type="nominal")
                        )
                        st.altair_chart(chart, use_container_width=True)
                    except ImportError:
                        st.info("Altair is required to view the pie charts.")


# Async Background Thread architecture for cross-thread sync proxying
@st.cache_resource
def get_async_executor():
    import threading
    loop = asyncio.new_event_loop()
    def _start_loop(l):
        asyncio.set_event_loop(l)
        l.run_forever()
    t = threading.Thread(target=_start_loop, args=(loop,), daemon=True)
    t.start()
    return loop

_bg_loop = get_async_executor()

def run_async(coroutine):
    future = asyncio.run_coroutine_threadsafe(coroutine, _bg_loop)
    return future.result()

# Use st.cache_resource to initialize the ADK runner and session service 
@st.cache_resource
def get_runner():
    from health_agent import HybridHealthAgent, server_path
    from google.adk.runners import Runner
    
    # Using Database for persistent memory capability!
    from google.adk.sessions.database_session_service import DatabaseSessionService
    from dotenv import load_dotenv
    load_dotenv()
    
    agent = HybridHealthAgent(
        name="SystemHealthMonitor",
        description="Hybrid system monitoring agent.",
        server_path=server_path
    )
    
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/health_db")
    session_service = DatabaseSessionService(db_url)
    
    runner = Runner(
        app_name="system_health_app",
        agent=agent,
        session_service=session_service,
    )
    return runner

# Start
st.set_page_config(page_title="System Monitor Dashboard (Streamlit)", layout="wide")
runner = get_runner()

def init_session():
    async def _init():
        app_name = "system_health_app"
        user_id = "admin"
        session_id = "streamlit_session"
        
        session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        if not session:
            session = await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
            
        history = []
        if hasattr(session, 'events') and session.events:
            for evt in session.events:
                text = "".join(p.text for p in evt.content.parts if p.text)
                if evt.author == "user":
                    history.append({"role": "user", "content": text})
                else:
                    history.append({"role": "assistant", "content": text})
        return session, history
    return run_async(_init())

st.title("System Monitor Dashboard")
st.markdown("Real-time diagnostics with interactive tools.")

if "session" not in st.session_state:
    session, history = init_session()
    st.session_state.session = session
    st.session_state.messages = history

app_session = st.session_state.session

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Quick Diagnostics")
    
    if st.button("CPU Usage", use_container_width=True):
        st.session_state.queued_prompt = "cpu"
        
    if st.button("RAM Usage", use_container_width=True):
        st.session_state.queued_prompt = "ram"
        
    st.divider()
    disk_path = st.text_input("Disk Path", value="C:\\" if os.name == "nt" else "/")
    if st.button("Disk Usage", use_container_width=True):
        st.session_state.queued_prompt = f"disk {disk_path}"
        
    st.divider()
    top_n = st.number_input("Top Tasks (N)", min_value=1, value=5)
    if st.button("Top Tasks", use_container_width=True):
        st.session_state.queued_prompt = f"top {top_n}"
        
    st.divider()
    st.markdown("##### Look up specific process")
    process_lookup_type = st.radio("Lookup By", options=["PID", "Name"], horizontal=True)
    process_val = st.text_input("Value")
    if st.button("Lookup Process", use_container_width=True):
        if process_lookup_type == "PID" and process_val:
            st.session_state.queued_prompt = f"pid {process_val}"
        elif process_lookup_type == "Name" and process_val:
            st.session_state.queued_prompt = f"name {process_val}"

with col2:
    st.subheader("Interactive Terminal")
    
    chat_container = st.container(height=500)
    
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                render_content(msg["content"])
                
    prompt = st.chat_input("Command (e.g. cpu, ram, top 5, pid 1234)")
    
    if "queued_prompt" in st.session_state and st.session_state.queued_prompt:
        prompt = st.session_state.queued_prompt
        st.session_state.queued_prompt = None

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                user_msg = types.Content(role="user", parts=[types.Part(text=prompt)])
                
                async def fetch_response():
                    res = ""
                    async for event in runner.run_async(session_id=app_session.id, user_id="admin", new_message=user_msg):
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    res += part.text
                    
                    return res
                
                with st.spinner("Executing command..."):
                    full_response = run_async(fetch_response())
                    
                render_content(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
