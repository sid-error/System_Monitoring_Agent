import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.tools.mcp_tool import McpToolset
from google.genai.types import Content, Part
from mcp import StdioServerParameters

script_dir = os.path.dirname(os.path.abspath(__file__))
server_path = os.path.join(script_dir, "health_server.py")

toolset = McpToolset(
    connection_params=StdioServerParameters(
        command="python",
        args=[server_path]
    )
)

agent = LlmAgent(
    name="SystemHealthMonitor",
    model="gemini-3.1-flash-lite-preview",
    instruction=(
        "You are a system health monitoring assistant. "
        "Use the provided tools to answer questions about CPU, RAM, disk usage, and top processes. "
        "For disk usage, if the user doesn't specify a drive, ask which drive (e.g., C: on Windows). "
        "You can look up specific processes by name or PID using the provided tools. "
        "Always format tabulated data, such as process lists or statistics, as proper Markdown tables."
    ),
    tools=[toolset],
)

db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/health_db")
session_service = DatabaseSessionService(db_url)

runner = Runner(
    app_name="system_health_app",
    agent=agent,
    session_service=session_service,
)

async def main():
    print(f"Connecting to database at {db_url}...")
    session = await session_service.get_session(app_name="system_health_app", user_id="admin", session_id="cli_session")
    if not session:
        session = await session_service.create_session(app_name="system_health_app", user_id="admin", session_id="cli_session")
    print("System Health Agent ready. Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError:
            break
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        user_message = Content(
            role="user",
            parts=[Part(text=user_input)]
        )
        try:
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
        except Exception as e:
            print(f"\n[Error communicating]: {e}")
            print("Please try your prompt again.")

if __name__ == "__main__":
    asyncio.run(main())