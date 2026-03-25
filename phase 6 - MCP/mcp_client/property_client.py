import contextlib
from google.genai import types
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class ToolManager:
    def __init__(self, server_script_path: str):
        # Notice we take the exact path as an argument now!
        self.server_params = StdioServerParameters(command="python", args=[server_script_path])
        self._stack = contextlib.AsyncExitStack()
        self.session = None

    async def connect(self):
        print("[TOOL MANAGER] Booting up the MCP Server...")
        transport = await self._stack.enter_async_context(stdio_client(self.server_params))
        self.session = await self._stack.enter_async_context(ClientSession(*transport))
        await self.session.initialize()
        print("[TOOL MANAGER] Connection established.")

    async def disconnect(self):
        await self._stack.aclose()
        print("[TOOL MANAGER] Disconnected safely.")

    async def get_menu_for_gemini(self) -> list:
        mcp_response = await self.session.list_tools()
        gemini_tools = []
        for tool in mcp_response.tools:
            func_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=tool.inputSchema 
            )
            gemini_tools.append(func_decl)
        return [types.Tool(function_declarations=gemini_tools)]

    async def execute(self, tool_name: str, tool_args: dict) -> str:
        print(f"[TOOL MANAGER] Executing '{tool_name}'...")
        result = await self.session.call_tool(tool_name, arguments=tool_args)
        return result.content[0].text