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
        if cmd == "cpu":
            return await self._call(tool_map, "get_cpu_usage", {})

        # RAM
        if cmd in ("ram", "memory", "mem"):
            return await self._call(tool_map, "get_ram_usage", {})

        # Disk
        if cmd.startswith("disk"):
            match = re.match(r"^disk\s+([a-zA-Z]:|[/\\]\w*)", raw, flags=re.IGNORECASE)
            path = match.group(1) if match else ("C:\\" if os.name == "nt" else "/")
            return await self._call(tool_map, "get_disk_usage", {"path": path})

        # Top Processes
        if cmd.startswith("top"):
            match = re.match(r"^top\s+(\d+)", cmd)
            n = int(match.group(1)) if match else 5
            return await self._call(tool_map, "get_top_processes", {"n": n})

        # Process details by ID
        if cmd.startswith("pid ") or cmd.startswith("id "):
            pid_match = re.match(r"^(?:pid|id)\s+(\d+)", cmd)
            if pid_match:
                return await self._call(tool_map, "get_process_details_by_id", {"pid": int(pid_match.group(1))})

        # Process details by name
        if cmd.startswith("name "):
            name_match = re.match(r"^name\s+(.+)", raw, flags=re.IGNORECASE)
            if name_match:
                return await self._call(tool_map, "get_process_details_by_name", {"name": name_match.group(1).strip()})

        # Fallback to general help or search
        return f"Unknown command: '{raw}'. Try 'cpu', 'ram', 'disk [path]', 'top [n]', 'pid [id]', 'name [process]', or ask a question."

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
            "- name [process]: Get process details by name\n"
        )

import typing
from pydantic import PrivateAttr

class HybridHealthAgent(BaseAgent):
    """
    A smart router agent. Attempts to use Gemini via LlmAgent first.
    If the API key is missing or the API errors out, gracefully drops back
    to the deterministic HealthBaseAgent.
    """
    server_path: str
    _fallback: typing.Any = PrivateAttr()
    _llm: typing.Any = PrivateAttr(default=None)

    def model_post_init(self, __context: typing.Any) -> None:
        self._fallback = HealthBaseAgent(name=f"{self.name}_fallback", description=self.description, server_path=self.server_path)
        
        from google.adk.agents import LlmAgent
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key.strip():
            # Setup LLM mapping to our existing MCP
            toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="python",
                        args=[self.server_path],
                    )
                )
            )
            self._llm = LlmAgent(
                name=f"{self.name}_llm",
                description=self.description,
                model="gemini-2.5-flash",
                tools=[toolset],
                instruction="You are a system health assistant. When requested, use your tools to analyze system metrics. If asked about CPU, RAM, or processes, fetch the data and present it cleanly."
            )

    def _make_event(self, ctx: InvocationContext, text: str):
        from google.adk.events import Event
        from google.genai import types
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=text)])
        )

    async def _run_async_impl(self, ctx: InvocationContext):
        user_text = ""
        if hasattr(ctx, "user_content") and ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if part.text:
                    user_text += part.text
        
        cmd = user_text.lower().strip()
        
        # Decide if we MUST route direct to base-agent (skipping LLM entirely)
        # e.g., explicit quick-diagnostics button presses.
        is_base = False
        if cmd in ("cpu", "ram", "memory", "mem", "help", "h", "?"):
            is_base = True
        elif cmd.startswith("disk") or cmd.startswith("top"):
            is_base = True
        elif cmd.startswith("pid ") or cmd.startswith("id ") or cmd.startswith("name "):
            is_base = True
        
        if is_base:
            async for event in self._fallback._run_async_impl(ctx):
                yield event
            return

        if self._llm:
            try:
                # Patch context so LLM knows it's the executing agent (bypassing Hybrid proxy context)
                patched_ctx = ctx.model_copy(update={"agent": self._llm}) if hasattr(ctx, "model_copy") else ctx.copy(update={"agent": self._llm})
                
                # Execute LLM logic naturally for abstract natural language prompt
                async for event in self._llm._run_async_impl(patched_ctx):
                    yield event
                return
            except Exception as e:
                print(f"\\n[Hybrid Agent] LLM failed ({e}). Yielding to fallback determinism.\\n")
                yield self._make_event(ctx, f"*(LLM API Error: {e}. Defaulting to Base Agent)*\\n")
        else:
            yield self._make_event(ctx, "*(GEMINI_API_KEY not found. Defaulting to Base Agent)*\\n")
        
        # If the prompt is totally out of scope, OR the LLM API is disconnected/failed:
        # Fall gracefully backward into the deterministic parser so it can run process name lookups!
        async for event in self._fallback._run_async_impl(ctx):
            yield event

# Runner setup
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService

load_dotenv()
script_dir = os.path.dirname(os.path.abspath(__file__))
server_path = os.path.join(script_dir, "health_server.py")

agent = HybridHealthAgent(
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
        
        user_evt = Event(invocation_id="cli", author="user", content=user_msg)
        await session_service.append_event(session, user_evt)
        
        async for event in runner.run_async(session_id=session.id, user_id="admin", new_message=user_msg):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
            await session_service.append_event(session, event)
        print()

if __name__ == "__main__":
    from dotenv import load_dotenv
    asyncio.run(main())
