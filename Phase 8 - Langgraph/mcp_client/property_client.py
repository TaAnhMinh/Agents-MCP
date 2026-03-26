import os
import contextlib
import sys
from google.genai import types
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class ToolManager:
    # 1. Accept a dictionary of servers instead of a single string!
    # Example: {"real_estate": "property_server.py", "finance": "finance_server.py"}
    def __init__(self, server_scripts: dict[str, str]):
        self.server_scripts = server_scripts
        self.server_env = os.environ.copy()
        
        self._stack = contextlib.AsyncExitStack()
        
        # 2. Store multiple sessions and our Routing Table
        self.sessions: dict[str, ClientSession] = {}
        self.tool_routing: dict[str, str] = {} # Maps tool_name -> server_name

    async def connect(self):
        print("[TOOL MANAGER] Booting up MCP Servers...")
        
        # 3. Loop through every server in the dictionary and boot them all!
        for server_name, script_path in self.server_scripts.items():
            print(f"   -> Starting '{server_name}' server...")
            params = StdioServerParameters(
                command=sys.executable, 
                args=[script_path], 
                env=self.server_env
            )
            transport = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(*transport))
            await session.initialize()
            
            # Save the active connection
            self.sessions[server_name] = session
            
        print("[TOOL MANAGER] All connections established.")

    async def disconnect(self):
        # AsyncExitStack beautifully closes ALL servers at once
        await self._stack.aclose()
        print("[TOOL MANAGER] All servers disconnected safely.")

    async def get_menu_for_gemini(self) -> list:
        gemini_tools = []
        
        # 4. Ask EVERY server for its tools and combine them
        for server_name, session in self.sessions.items():
            mcp_response = await session.list_tools()
            
            for tool in mcp_response.tools:
                # THE ROUTING TABLE: Write down who owns this tool!
                self.tool_routing[tool.name] = server_name
                
                func_decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.inputSchema 
                )
                gemini_tools.append(func_decl)
                
        # Gemini gets one massive, unified menu
        return [types.Tool(function_declarations=gemini_tools)]

    async def execute(self, tool_name: str, tool_args: dict) -> str:
        # 5. Look up the tool in our routing table
        target_server = self.tool_routing.get(tool_name)
        
        if not target_server:
            return f"Error: Tool '{tool_name}' not found on any connected server."
            
        print(f"[TOOL MANAGER] Routing '{tool_name}' execution to the '{target_server}' server...")
        
        # Grab the correct session and fire the tool!
        session = self.sessions[target_server]
        result = await session.call_tool(tool_name, arguments=tool_args)
        return result.content[0].text