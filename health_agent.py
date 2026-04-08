import os
import psutil
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# ---------- Tools ----------
def get_cpu_usage() -> str:
    """Returns current CPU usage percentage."""
    return f"CPU usage: {psutil.cpu_percent(interval=1)}%"

def get_ram_usage() -> str:
    """Returns RAM usage details (total, used, free, percentage)."""
    mem = psutil.virtual_memory()
    return (f"RAM - Total: {mem.total // (1024**3)} GB, "
            f"Used: {mem.used // (1024**3)} GB, "
            f"Free: {mem.free // (1024**3)} GB, "
            f"Usage: {mem.percent}%")

def get_top_processes(n: int = 5) -> str:
    """Returns top N processes by CPU usage.
    Args:
        n: Number of top processes to return (default 5)
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            proc_info = proc.info
            processes.append(proc_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    top_n = processes[:n]
    result = f"Top {n} processes by CPU usage:\n"
    for p in top_n:
        result += f"PID {p['pid']}: {p['name']} - {p['cpu_percent']}%\n"
    return result

# ---------- Agent ----------
agent = LlmAgent(
    name="SystemHealthMonitor",
    model="gemini-2.5-flash",
    instruction=(
        "You are a system health monitoring assistant. "
        "Use the provided tools to answer user questions about CPU, RAM, and processes. "
        "When asked about system health, call the appropriate tools and present the data clearly."
    ),
    tools=[get_cpu_usage, get_ram_usage, get_top_processes],
)

# ---------- Session,State & Runner ----------
session_service = InMemorySessionService()
runner = Runner(
    app_name="system_health_app",
    agent=agent,
    session_service=session_service,
)

async def main():
    session = await session_service.create_session(
        app_name="system_health_app",
        user_id="admin",
    )
    
    user_message = Content(
        role="user",
        parts=[Part(text="What is my CPU and RAM usage? Also show top 3 processes.")]
    )
    
    async for event in runner.run_async(
        session_id=session.id,
        user_id="admin",
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(part.text, end="", flush=True)
    print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())