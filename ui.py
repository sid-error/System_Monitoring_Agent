import streamlit as st
import asyncio
from google.genai.types import Content, Part
import os
import io
import re
import pandas as pd
import altair as alt
import threading
from health_agent import runner

if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="System Health Monitor", page_icon="🖥️", layout="wide")
st.title("🖥️ System Health Monitor")
st.write("A conversational agent powered by Google ADK + MCP to monitor your system and visually chart your system load.")

APP_NAME = "system_health_app"
USER_ID = "admin"
SESSION_ID = "streamlit_session"

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

def render_markdown_with_charts(text):
    """
    Scans the markdown text for tabular structures, renders preceding markdown normally,
    then evaluates the table as a dynamic Pandas DataFrame, and injects a Streamlit Chart automatically.
    """
    # Regex to capture markdown tables. It looks for lines having at least two pipes.
    table_pattern = re.compile(r'(?:\|[^\n]+\|\n?)+')
    
    last_end = 0
    for match in table_pattern.finditer(text):
        plain_text = text[last_end:match.start()]
        if plain_text.strip():
            st.markdown(plain_text)
            
        table_str = match.group(0).strip()
        last_end = match.end()
        
        try:
            # Reformat markdown table to CSV
            lines = []
            for line in table_str.split('\n'):
                line = line.strip(" |")
                # Remove header separator (e.g. |---|---|)
                if re.match(r'^[-:| ]+$', line):
                    continue
                # Replace inner pipes with comma
                csv_line = re.sub(r'\s*\|\s*', ',', line)
                lines.append(csv_line)
                
            csv_like = "\n".join(lines)
            df = pd.read_csv(io.StringIO(csv_like))
            df.columns = df.columns.str.strip()
            
            # Clean generic properties attached to units natively returned by the AI (e.g. '15 GB' -> 15.0 or '37.4%' -> 37.4)
            for col in df.columns:
                try:
                    if df[col].astype(str).str.match(r'^\s*[\d\.]+\s*(?:%|[a-zA-Z]+)?\s*$').all():
                        extracted = df[col].astype(str).str.extract(r'([\d\.]+)', expand=False)
                        if extracted.notna().any():
                            df[col] = extracted.astype(float)
                except Exception:
                    pass

            st.markdown("### 📊 Tabular Data View")
            st.dataframe(df, use_container_width=True)
            
            # Auto-detect if we can chart this!
            if len(df.columns) >= 2:
                # Use the first text/string column as the X-Axis index if possible
                string_cols = df.select_dtypes(include=['object', 'string']).columns
                index_col = string_cols[0] if len(string_cols) > 0 else df.columns[0]
                
                chart_df = df.set_index(index_col)
                # Ensure we strictly don't plot IDs!
                raw_num_cols = chart_df.select_dtypes(include=['number']).columns
                num_cols = [c for c in raw_num_cols if 'id' not in c.lower() and 'pid' not in c.lower()]
                
                if len(num_cols) > 0:
                    st.markdown("### 📈 Visual Representation")
                    
                    # Detect logical RAM / Disk categorical components for Pie Chart Representation
                    index_lower = chart_df.index.astype(str).str.lower()
                    if any('used' in idx for idx in index_lower) and any('free' in idx for idx in index_lower):
                        # Construct a Pie Chart
                        pie_df = chart_df[~index_lower.isin(['total', 'usage', 'usage%', 'usage %'])]
                        
                        # Reset Index so Altair can target the Columns structurally
                        pie_df = pie_df.reset_index()
                        first_cat = pie_df.columns[0]
                        first_num = num_cols[0]
                        
                        pie_chart = alt.Chart(pie_df).mark_arc(innerRadius=40).encode(
                            theta=alt.Theta(field=first_num, type="quantitative"),
                            color=alt.Color(field=first_cat, type="nominal"),
                            tooltip=[first_cat, first_num]
                        ).properties(height=350)
                        
                        st.altair_chart(pie_chart, use_container_width=True)
                    else:
                        st.bar_chart(chart_df[num_cols])
                        
        except Exception as e:
            # Better safe than sorry. If Pandas drops the ball on charting, log the error and drop fallback markdown 
            print(f"DEBUG: Chart Error Exception: {e}")
            st.markdown(table_str)
            
    # Render trailing text
    remaining_text = text[last_end:]
    if remaining_text.strip():
        st.markdown(remaining_text)

# Chat UI
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    role = msg.get("role")
    with st.chat_message("user" if role == "user" else "assistant"):
        if role == "assistant":
            render_markdown_with_charts(msg.get("text"))
        else:
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
                render_markdown_with_charts(response_text)
                st.session_state.history.append({"role": "assistant", "text": response_text})
            except Exception as e:
                st.error(f"Error connecting to agent backend: {e}")
