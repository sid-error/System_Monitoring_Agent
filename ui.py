import streamlit as st
import asyncio
from google.genai.types import Content, Part
import os
from health_agent import runner

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="System Health Monitor", page_icon="🖥️")
st.title("🖥️ System Health Monitor")
st.write("A conversational agent powered by Google ADK + MCP to monitor your system.")

APP_NAME = "system_health_app"
USER_ID = "admin"
SESSION_ID = "streamlit_session"

import threading

@st.cache_resource
def get_or_create_eventloop():
    loop = asyncio.new_event_loop()
    def start_loop(l):
        asyncio.set_event_loop(l)
        try:
            l.run_forever()
        finally:
            l.close()
    t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
    t.start()
    return loop

loop = get_or_create_eventloop()

async def get_or_create_session():
    session = await runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    if not session:
        session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    return session

async def process_message(user_input: str):
    session = await get_or_create_session()
    user_message = Content(role="user", parts=[Part(text=user_input)])
    full_response = ""
    async for event in runner.run_async(session_id=session.id, user_id=USER_ID, new_message=user_message):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    full_response += part.text
    return full_response

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

# Chat UI
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    role = msg.get("role")
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(msg.get("text"))

user_input = st.chat_input("Ask about CPU, RAM, Disk, or Processes...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.history.append({"role": "user", "text": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing system health via MCP tools..."):
            try:
                response_text = run_async(process_message(user_input))
                st.markdown(response_text)
                st.session_state.history.append({"role": "agent", "text": response_text})
            except Exception as e:
                st.error(f"Error connecting to agent backend: {e}")