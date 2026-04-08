import os
import psutil
import time
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# ---------- Tools ----------
def get_cpu_usage() -> str:
    return f"CPU usage: {psutil.cpu_percent(interval=1)}%"

def get_ram_usage() -> str:
    mem = psutil.virtual_memory()
    return (f"RAM - Total: {mem.total // (1024**3)} GB, "
            f"Used: {mem.used // (1024**3)} GB, "
            f"Free: {mem.free // (1024**3)} GB, "
            f"Usage: {mem.percent}%")

def get_disk_usage(path: str = "/") -> str:
    """Returns disk usage for a given path (e.g., 'C:' on Windows, '/' on Linux).
    Args:
        path: Drive or mount point (e.g., 'C:' or '/')
    """
    if os.name == 'nt':
        if len(path) == 2 and path[1] == ':':
            path = path + "\\"
        if path.endswith(':'):
            path = path + "\\"
    try:
        usage = psutil.disk_usage(path)
        return (f"Disk {path}: Total: {usage.total // (1024**3)} GB, "
                f"Used: {usage.used // (1024**3)} GB, "
                f"Free: {usage.free // (1024**3)} GB, "
                f"Usage: {usage.percent}%")
    except FileNotFoundError:
        return f"Error: Drive or path '{path}' not found. Please specify an existing drive (e.g., 'C:' on Windows)."
    except PermissionError:
        return f"Error: Permission denied for path '{path}'."
    except Exception as e:
        return f"Error checking disk usage: {str(e)}"

def get_top_processes(n: int = 5) -> str:
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc.cpu_percent(interval=0)
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.5)
    proc_data = []
    for proc in processes:
        try:
            if proc.info['name'] == "System Idle Process":
                continue
            cpu_percent = proc.cpu_percent(interval=0)
            proc_data.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'] or 'Unknown',
                'cpu_percent': cpu_percent
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    proc_data.sort(key=lambda x: x['cpu_percent'], reverse=True)
    top_n = proc_data[:n]
    result = f"Top {n} processes by CPU usage (over 0.5s):\n"
    for p in top_n:
        result += f"PID {p['pid']}: {p['name']} - {p['cpu_percent']:.1f}%\n"
    return result

# ---------- Agent ----------
agent = LlmAgent(
    name="SystemHealthMonitor",
    model="gemini-2.5-flash",
    instruction=(
        "You are a system health monitoring assistant. "
        "Use the provided tools to answer questions about CPU, RAM, disk usage, and top processes. "
        "For disk usage, if the user doesn't specify a drive, ask which drive (e.g., C: on Windows)."
    ),
    tools=[get_cpu_usage, get_ram_usage, get_disk_usage, get_top_processes],
)

session_service = InMemorySessionService()
runner = Runner(
    app_name="system_health_app",
    agent=agent,
    session_service=session_service,
)

# ---------- Interactive Main ----------
async def main():
    session = await session_service.create_session(
        app_name="system_health_app",
        user_id="admin",
    )
    print("System Health Agent ready. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        user_message = Content(
            role="user",
            parts=[Part(text=user_input)]
        )
        print("Agent: ", end="")
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