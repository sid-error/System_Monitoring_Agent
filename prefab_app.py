import os
import sys
import json
import re
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

# Robust Fix for Windows Unicode printing
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, Row, Heading, Text, Button, Input, Card, CardContent, ForEach, If, Else, Markdown
from prefab_ui.components.charts import BarChart, PieChart, ChartSeries
from prefab_ui.components import DataTable, DataTableColumn
from prefab_ui.actions import SetState, CallHandler
from prefab_ui.actions.mcp import SendMessage
from prefab_ui.rx import STATE, ITEM

from google.genai.types import Content, Part
from health_agent import runner

load_dotenv()

APP_NAME = "system_health_app"
USER_ID = "admin"
SESSION_ID = "prefab_interactive_session"

def parse_json_blocks(text: str) -> List[Dict]:
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

async def fetch_history_async():
    """Asynchronously fetches history from the DB."""
    welcome = [{"role": "agent", "components": [{"type": "text", "content": "Welcome! System Monitoring Agent is ready. Click the buttons above to trigger diagnostics."}]}]
    try:
        history = await runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
        if not history:
            history = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
        
        if history and hasattr(history, 'history') and history.history:
            messages = []
            for msg in history.history:
                text = "".join(p.text for p in msg.parts if p.text)
                if msg.role == "user":
                    messages.append({"role": "user", "content": text})
                else:
                    messages.append({"role": "agent", "components": parse_json_blocks(text)})
            return messages
        return welcome
    except:
        return welcome

# Initial state (placeholders, will be re-hydrated by adk web)
app = PrefabApp(
    title="System Monitor Dashboard",
    state={
        "messages": [], 
        "new_prompt": "", 
        "disk_path": "C:\\" if os.name == "nt" else "/",
        "top_n": "5",
        "debug_status": "Ready"
    },
    css_class="p-6 max-w-6xl mx-auto dark bg-slate-950 min-h-screen text-slate-100"
)

with app:
    with Column(css_class="mb-8"):
        Heading("System Monitoring Agent", size="h1", css_class="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400")
        Text("Real-time diagnostics with interactive charts and tables.", css_class="text-slate-400 text-lg mb-2")
        
        # STATUS STRIP
        with Card(css_class="bg-slate-900 border-yellow-900/30 mb-4 shadow-xl"):
            with CardContent(css_class="p-4 flex justify-between items-center"):
                with Row(gap=2, css_class="items-center"):
                    Text("System Status: ", css_class="text-xs text-slate-500 uppercase font-bold")
                    Text(STATE.debug_status, css_class="text-xs text-emerald-500 font-mono font-bold")
                Button("Verify UI Action", 
                    actions=[SetState("debug_status", "CONNECTION VERIFIED (UI REACTIVITY ACTIVE)")], 
                    css_class="text-[10px] bg-slate-800 px-4 py-2 rounded-lg border border-slate-700 hover:bg-slate-700 transition-all uppercase font-bold text-slate-300"
                )

    # QUICK ACTIONS FORM
    with Card(css_class="bg-slate-900 border-slate-800 mb-8 border-t-4 border-t-blue-500 shadow-2xl"):
        with CardContent(css_class="p-6"):
            Heading("Quick Diagnostics", size="h3", css_class="mb-6 text-blue-300 font-bold")
            with Row(gap=4, css_class="flex-wrap"):
                Button("CPU Usage", 
                    actions=[SendMessage("cpu")],
                    css_class="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-xl font-bold transition-all shadow-lg active:scale-95 flex-grow"
                )
                Button("RAM Usage", 
                    actions=[SendMessage("ram")],
                    css_class="bg-emerald-600 hover:bg-emerald-500 text-white px-8 py-3 rounded-xl font-bold transition-all shadow-lg active:scale-95 flex-grow"
                )
                with Row(gap=2, css_class="items-center bg-slate-800 p-2 rounded-xl border border-slate-700 flex-grow"):
                    Input(name="disk_path", placeholder="Path", css_class="bg-transparent border-none w-24 text-sm px-4 focus:ring-0")
                    Button("Disk", 
                        actions=[SendMessage("disk " + STATE.disk_path)],
                        css_class="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg font-bold transition-all active:scale-95"
                    )
                with Row(gap=2, css_class="items-center bg-slate-800 p-2 rounded-xl border border-slate-700 flex-grow"):
                    Input(name="top_n", placeholder="N", css_class="bg-transparent border-none w-12 text-sm px-4 focus:ring-0")
                    Button("Top Tasks", 
                        actions=[SendMessage("top " + STATE.top_n)],
                        css_class="bg-amber-600 hover:bg-amber-500 text-white px-6 py-2 rounded-lg font-bold transition-all active:scale-95"
                    )

    # OUTPUT AREA
    with Column(gap=6, css_class="max-h-[800px] overflow-y-auto pr-4 custom-scrollbar"):
        with ForEach(key=STATE.messages):
            with If(condition=ITEM.role == "user"):
                with Row(css_class="justify-end mb-2"):
                    with Card(css_class="bg-blue-900/40 border-blue-800 rounded-2xl rounded-tr-none shadow-md"):
                        with CardContent(css_class="px-6 py-3"):
                            Text(ITEM.content, css_class="text-blue-100 font-medium")
            with Else():
                with Row(css_class="justify-start mb-6"):
                    with Column(css_class="w-full"):
                        with ForEach(key=ITEM.components):
                            with If(condition=ITEM.type == "text"):
                                with Card(css_class="bg-slate-900 border-slate-800 mb-2 shadow-sm"):
                                    with CardContent(css_class="p-5"):
                                        Markdown(ITEM.content)
                            with Else():
                                with Card(css_class="bg-slate-900 border-slate-700 shadow-2xl mb-4 overflow-hidden rounded-2xl"):
                                    with CardContent(css_class="p-0"):
                                        with Column(css_class="p-5 border-b border-slate-800 bg-slate-900/90"):
                                            Heading("Diagnostic Intelligence", size="h4", css_class="text-blue-400 font-extrabold")
                                        
                                        with Column(css_class="p-8 text-slate-100"):
                                            with If(condition=ITEM.chart_type == "bar"):
                                                BarChart(
                                                    data=ITEM.data,
                                                    series=[ChartSeries(data_key=str(ITEM.y_axis), label=str(ITEM.y_axis), color="#3b82f6")],
                                                    x_axis=str(ITEM.x_axis),
                                                    css_class="h-80"
                                                )
                                            with If(condition=ITEM.chart_type == "pie"):
                                                PieChart(
                                                    data=ITEM.data,
                                                    data_key=str(ITEM.y_axis),
                                                    name_key=str(ITEM.x_axis),
                                                    css_class="h-80"
                                                )
                                        
                                        with Column(css_class="p-4 bg-slate-950/80 border-t border-slate-800"):
                                            DataTable(
                                                data=ITEM.data,
                                                columns=[DataTableColumn(key="Category", header="Category"), DataTableColumn(key="Gigabytes", header="GB"), DataTableColumn(key="Metric", header="Metric"), DataTableColumn(key="Percentage", header="%"), DataTableColumn(key="Process Name", header="Name"), DataTableColumn(key="CPU Usage", header="CPU %")],
                                                css_class="border-transparent"
                                            )

    # CHAT BOX
    with Row(gap=3, css_class="mt-10 pt-6 border-t border-slate-800"):
        Input(name="new_prompt", placeholder="Describe a custom system check...", css_class="flex-grow bg-slate-900 border-slate-700 rounded-2xl px-6 py-4 outline-none focus:border-blue-500 transition-all shadow-inner")
        Button("Send Command", actions=[
            SendMessage(STATE.new_prompt),
            SetState("new_prompt", "")
        ], css_class="bg-blue-700 hover:bg-blue-600 text-white font-extrabold px-10 rounded-2xl transition-all border border-blue-600 shadow-2xl active:scale-95")

# --- STANDALONE SERVER SUPPORT ---
if __name__ == "__main__":
    from fastapi import FastAPI, Response
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn

    server = FastAPI()
    
    # Enable CORS
    server.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @server.get("/")
    async def index():
        # Force exact HTML content with the required mounting point
        html = app.html()
        # Ensure #root is present just in case the library version is behaving weirdly
        if 'id="root"' not in html:
            html = html.replace("<body>", '<body><div id="root"></div>')
        return Response(content=html, media_type="text/html")

    print("\n🚀 System Monitor Dashboard starting on http://localhost:8000")
    print("💡 Note: Use 'adk web prefab_app.py' for full ADK agent features.")
    uvicorn.run(server, host="0.0.0.0", port=8000)
else:
    # When imported by adk web or prefab serve, the 'app' object is used directly.
    pass
