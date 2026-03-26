import asyncio
import os
import json
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from mcp_client.property_client import ToolManager
from agent.property_agent import PropertyAgent


# ==========================================
# 1. DEFINE BOB'S JSON SCHEMA
# ==========================================
class BobOutput(BaseModel):
    property_id: str = Field(description="The ID of the property found")
    price: float = Field(description="The exact price of the property as a number")
    description_summary: str = Field(description="A strict 1-sentence summary of the property")

class AliceOutput(BaseModel):
    is_approved: bool = Field(description="Set to True if Nancy's math makes sense. Set to False if the math is missing, broken, or mathematically impossible.")
    legal_report: str = Field(description="The final legal summary, or an explanation of why the math was rejected.")

# ==========================================
# 1. DEFINE THE STATE (The Shared Clipboard)
# ==========================================
class TeamState(TypedDict):
    user_request: str
    bob_draft: str
    nancy_draft: str
    nancy_approved: bool
    final_report: str
    alice_approved: bool

# ==========================================
# 2. DEFINE THE NODES (The Factory Workers)
# ==========================================
# Notice how each node takes the clipboard (state), reads what it needs, 
# and returns a dictionary to update the clipboard for the next person.

async def bob_node(state: TeamState):
    print("\n[GRAPH] Routing to Bob...")
    
    # Bob will now return a JSON string!
    raw_json_reply = await bob_agent.chat(state["user_request"])
    print(f"   -> [BOB'S RAW OUTPUT]: {raw_json_reply}")
    
    # We can parse it into a standard Python dictionary to pass to Nancy
    parsed_reply = json.loads(raw_json_reply)
    
    # Write the clean JSON string to the clipboard
    return {"bob_draft": raw_json_reply} 

async def nancy_node(state: TeamState):
    print("\n[GRAPH] Routing to Nancy...")
    
    # Nancy can now read exact data keys instead of parsing a paragraph!
    bob_data = json.loads(state['bob_draft'])
    prompt = f"The user asked: '{state['user_request']}'. Bob found a house that costs ${bob_data['price']}. Please do the mortgage math."
    
    reply = await nancy_agent.chat(prompt)
    return {"nancy_draft": reply, "nancy_approved": True}

async def alice_node(state: TeamState):
    print("\n[GRAPH] Routing to Alice...")
    
    prompt = f"Nancy calculated this: '{state['nancy_draft']}'. Provide a brief legal review. If Nancy's math is missing or completely wrong, reject it."
    
    # Alice returns a JSON string based on our schema
    raw_json_reply = await alice_agent.chat(prompt)
    print(f"   -> [ALICE'S RAW OUTPUT]: {raw_json_reply}")
    
    # Parse the JSON
    alice_data = json.loads(raw_json_reply)
    
    # Dynamically set the clipboard based on Alice's AI decision!
    return {
        "final_report": alice_data["legal_report"],
        "alice_approved": alice_data["is_approved"]
    }

def nancy_quality_control(state: TeamState):
    if state["nancy_approved"] == True:
        return "Alice"  # The math is good, send to legal!
    else:
        return "Bob"
    
def quality_control_router(state: TeamState):
    if state["alice_approved"] == True:
        return END
    else:
        return "Bob"

# ==========================================
# 3. ORCHESTRATE THE GRAPH (The Assembly Line)
# ==========================================
async def run_graph():
    print("========================================")
    print("  BOOTING LANGGRAPH MAS ORCHESTRATOR    ")
    print("========================================\n")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    server_fleet = {
        "property": os.path.join(base_dir, "mcp_server", "property_server.py"),
        # You could instantly add a new server here tomorrow!
        # "weather": os.path.join(base_dir, "mcp_server", "weather_server.py") 
    }
    mcp_tools = ToolManager(server_scripts=server_fleet)
    
    try:
        await mcp_tools.connect()
        
        # 1. Hire the team globally so the nodes can see them
        global bob_agent, nancy_agent, alice_agent
        bob_agent = PropertyAgent(
            name="Bob", 
            role="Senior Real Estate Realtor", 
            tool_manager=mcp_tools,
            response_schema=BobOutput # <-- Force Bob to output JSON!
        )
        nancy_agent = PropertyAgent("Nancy", "Mortgage Broker", mcp_tools)
        alice_agent = PropertyAgent(
            name="Alice", 
            role="Legal Reviewer", 
            tool_manager=mcp_tools, 
            response_schema=AliceOutput
        )
        
        # 2. Build the Graph
        print("[GRAPH] Assembling the pipeline...")
        builder = StateGraph(TeamState)
        
        builder.add_node("Bob", bob_node)
        builder.add_node("Nancy", nancy_node)
        builder.add_node("Alice", alice_node)
        
        # 3. Draw the lines connecting them
        builder.add_edge(START, "Bob")
        builder.add_edge("Bob", "Nancy")
        builder.add_conditional_edges(
            "Nancy",                 
            nancy_quality_control    
        )
        builder.add_conditional_edges(
            "Alice",                
            quality_control_router    
        )
        
        # 4. Compile the engine
        app = builder.compile()

        # 5. Kick off the workflow!
        user_prompt = "I have two large dogs and need a place with a huge yard. Can you guys help me figure out what I'm looking at financially?"
        print(f"\nUSER: {user_prompt}")
        
        initial_clipboard = {
            "user_request": user_prompt,
            "bob_draft": "",
            "nancy_draft": "",
            "nancy_approved": False,
            "final_report": "",
            "alice_approved": False
        }

        # app.ainvoke automatically pushes the clipboard through the entire graph!
        final_state = await app.ainvoke(initial_clipboard)

        print("\n========================================")
        print("  FINAL TEAM REPORT")
        print("========================================")
        print(final_state["final_report"])

    finally:
        await mcp_tools.disconnect()

if __name__ == "__main__":
    asyncio.run(run_graph())