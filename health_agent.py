import os
import re
import asyncio
import json
from dotenv import load_dotenv
from typing import AsyncGenerator, Dict, Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

class HealthBaseAgent(BaseAgent):
    """
    A deterministic system-health agent subclass of BaseAgent.
    Routes commands directly to MCP tools without an LLM.
    """

    server_path: str

    def _make_event(self, ctx: InvocationContext, text: str) -> Event:
        """Wraps text/JSON into an ADK Event."""
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(
                role="model",
                parts=[types.Part(text=text)],
            ),
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        user_text = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if part.text:
                    user_text += part.text
        user_text = user_text.strip()

        if not user_text:
            yield self._make_event(ctx, "Please select an option or enter a command. Type 'help' for info.")
            return

        # MCP Toolset setup
        toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=[self.server_path],
                )
            )
        )

        try:
            tools = await toolset.get_tools()
            tool_map = {t.name: t for t in tools}
            
            # Dispatch
            cmd = user_text.lower()
            result = await self._dispatch(cmd, user_text, tool_map)
            
            # If the result is JSON, wrap it in a markdown block for the UI to parse
            if result.strip().startswith("{") and result.strip().endswith("}"):
                final_output = f"```json\n{result}\n```"
            else:
                final_output = result

            yield self._make_event(ctx, final_output)

        except Exception as exc:
            yield self._make_event(ctx, f"[Error] {exc}")
        finally:
            await toolset.close()

    async def _dispatch(self, cmd: str, raw: str, tool_map: Dict[str, Any]) -> str:
        """Processes the command and calls the appropriate tool."""
        
        # Help
        if cmd in ("help", "h", "?"):
            return self._help_text()

        # CPU
        if "cpu" in cmd:
            return await self._call(tool_map, "get_cpu_usage", {})

        # RAM
        if any(x in cmd for x in ("ram", "memory", "mem")):
            return await self._call(tool_map, "get_ram_usage", {})

        # Disk
        if "disk" in cmd:
            match = re.search(r"disk\s+([a-zA-Z]:|[/\\]\w*)", raw)
            path = match.group(1) if match else ("C:\\" if os.name == "nt" else "/")
            return await self._call(tool_map, "get_disk_usage", {"path": path})

        # Top Processes
        if "top" in cmd or "process" in cmd:
            match = re.search(r"(\d+)", cmd)
            n = int(match.group(1)) if match else 5
            return await self._call(tool_map, "get_top_processes", {"n": n})

        # Process details by ID
        pid_match = re.search(r"pid\s+(\d+)", cmd)
        if pid_match:
            return await self._call(tool_map, "get_process_details_by_id", {"pid": int(pid_match.group(1))})

        # Process details by name (Fallback if not a standard command)
        if raw and not raw.startswith("disk") and not raw.startswith("top"):
            # If the user typed something like "chrome" or "brave", route it to name search.
            return await self._call(tool_map, "get_process_details_by_name", {"name": raw})

        # Fallback to general help or search
        return f"Unknown command: '{raw}'. Try 'cpu', 'ram', 'disk [path]', 'top [n]', 'pid [id]', or a process name."

    async def _call(self, tool_map: Dict[str, Any], tool_name: str, args: Dict[str, Any]) -> str:
        tool = tool_map.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
        
        result = await tool.run_async(args=args, tool_context=None)
        
        # Standardize output string
        if isinstance(result, list):
            return "\n".join(getattr(item, "text", str(item)) for item in result)
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                return "\n".join(item.get("text", str(item)) for item in content if isinstance(item, dict))
            return str(content)
        return str(result)

    @staticmethod
    def _help_text() -> str:
        return (
            "Available Commands:\n"
            "- cpu: Check CPU usage\n"
            "- ram: Check RAM usage\n"
            "- disk [path]: Check disk usage (e.g. disk C:)\n"
            "- top [n]: List top n processes\n"
            "- pid [id]: Get process details\n"
        )

# Runner setup
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService

load_dotenv()
script_dir = os.path.dirname(os.path.abspath(__file__))
server_path = os.path.join(script_dir, "health_server.py")

agent = HealthBaseAgent(
    name="SystemHealthMonitor",
    description="Deterministic system monitoring agent.",
    server_path=server_path
)

db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/health_db")
session_service = DatabaseSessionService(db_url)

runner = Runner(
    app_name="system_health_app",
    agent=agent,
    session_service=session_service,
)

async def main():
    session = await session_service.get_session(app_name="system_health_app", user_id="admin", session_id="cli_session")
    if not session:
        session = await session_service.create_session(app_name="system_health_app", user_id="admin", session_id="cli_session")
    
    print("Health BaseAgent CLI ready. Type 'quit' to exit.")
    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError: break
        if user_input.lower() in ('quit', 'q', 'exit'): break
        if not user_input: continue

        user_msg = types.Content(role="user", parts=[types.Part(text=user_input)])
        print("Agent: ", end="", flush=True)
        async for event in runner.run_async(session_id=session.id, user_id="admin", new_message=user_msg):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
        print()

if __name__ == "__main__":
    from dotenv import load_dotenv
    asyncio.run(main())
