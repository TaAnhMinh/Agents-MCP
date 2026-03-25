import asyncio
import os

# 1. Clean Imports using folder routing!
from mcp_client.property_client import ToolManager
from agent.property_agent import PropertyAgent

async def run_mas():
    print("========================================")
    print("  BOOTING DECOUPLED MAS ENGINE          ")
    print("========================================\n")

    # 2. Bulletproof Pathing: 
    # This ensures the client can find the server folder no matter where you run the script from!
    base_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(base_dir, "mcp_server", "property_server.py")

    # 3. Instantiate the isolated components
    mcp_tools = ToolManager(server_script_path=server_path)
    
    try:
        # Boot up the server connection
        await mcp_tools.connect()
        
        # Inject the ToolManager into the Agent
        bob = PropertyAgent(name="Bob", role="Senior Real Estate Expert", tool_manager=mcp_tools)
        
        # Run the conversation
        reply_1 = await bob.chat("I have a $550,000 budget. Find me a home.")
        print(f"\nBOB: {reply_1}")
        print("-" * 40)
        
        reply_2 = await bob.chat("What's my monthly payment on that at 7% for 30 years?")
        print(f"\nBOB: {reply_2}")
        
    finally:
        # Guarantee the server shuts down cleanly even if the code crashes
        await mcp_tools.disconnect()

if __name__ == "__main__":
    asyncio.run(run_mas())