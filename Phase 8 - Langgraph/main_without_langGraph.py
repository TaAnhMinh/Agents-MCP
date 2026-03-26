import asyncio
import os

from mcp_client.property_client import ToolManager
from agent.property_agent import PropertyAgent

async def run_mas():
    print("========================================")
    print("  BOOTING MANUAL MULTI-AGENT PIPELINE   ")
    print("========================================\n")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(base_dir, "mcp_server", "property_server.py")

    mcp_tools = ToolManager(server_script_path=server_path)
    
    try:
        await mcp_tools.connect()
        
        # ==========================================
        # 1. HIRE THE TEAM (Using the same blueprint!)
        # ==========================================
        bob = PropertyAgent(
            name="Bob", 
            role="Senior Real Estate Realtor. Find a property matching the user's needs.", 
            tool_manager=mcp_tools
        )
        
        nancy = PropertyAgent(
            name="Nancy", 
            role="Mortgage Broker. Calculate the monthly payment for the property Bob found. Assume 6.5% interest over 30 years.", 
            tool_manager=mcp_tools
        )
        
        alice = PropertyAgent(
            name="Alice", 
            role="Legal Reviewer. Summarize the financial commitment based on Nancy's math and add a standard legal warning.", 
            tool_manager=mcp_tools
        )
        
        # ==========================================
        # 2. THE MANUAL PIPELINE
        # ==========================================
        user_prompt = "I have a couple of dogs and need a place with space. Can you guys help me figure out what I'm looking at financially?"
        print(f"USER: {user_prompt}\n")
        
        # --- BOB'S TURN ---
        print("--- BOB'S TURN ---")
        bob_reply = await bob.chat(user_prompt)
        print(f"\nBOB: {bob_reply}\n")
        
        # --- NANCY'S TURN ---
        print("--- NANCY'S TURN ---")
        # Notice how we have to manually write a prompt explaining what Bob did!
        nancy_prompt = f"The user asked: '{user_prompt}'. Bob found this property: '{bob_reply}'. Please do your mortgage calculation."
        nancy_reply = await nancy.chat(nancy_prompt)
        print(f"\nNANCY: {nancy_reply}\n")
        
        # --- ALICE'S TURN ---
        print("--- ALICE'S TURN ---")
        # We have to manually pass Nancy's math to Alice
        alice_prompt = f"Nancy calculated this: '{nancy_reply}'. Please provide the legal review."
        alice_reply = await alice.chat(alice_prompt)
        print(f"\nALICE: {alice_reply}\n")
        
    finally:
        await mcp_tools.disconnect()

if __name__ == "__main__":
    asyncio.run(run_mas())