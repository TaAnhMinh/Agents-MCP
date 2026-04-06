import asyncio
import os
import json
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from mcp_client.property_client import ToolManager
from agent.property_agent import PropertyAgent
from langgraph.checkpoint.memory import MemorySaver


# ==========================================
# 1. DEFINE BOB'S JSON SCHEMA
# ==========================================
class BobOutput(BaseModel):
    property_id: str = Field(description="The ID of the property found")
    price: float = Field(description="The exact price of the property as a number")
    description_summary: str = Field(description="A strict 1-sentence summary of the property")

class AliceOutput(BaseModel):
    is_approved: bool = Field(description="Set to True if Nancy's math makes sense and the human approve the selection of the property. Set to False if the math is missing, broken, or mathematically impossible, or the human does not approve the selection of the property.")
    legal_report: str = Field(description="The final legal summary, or an explanation of why the math was rejected.")

# ==========================================
# 1. DEFINE THE STATE (The Shared Clipboard)
# ==========================================
class TeamState(TypedDict):
    user_request: str
    bob_draft: str
    rejected_properties: list[str]
    nancy_draft: str
    nancy_approved: bool
    human_feedback: str
    final_report: str
    alice_approved: bool

# ==========================================
# 2. DEFINE THE NODES (The Factory Workers)
# ==========================================
# Notice how each node takes the clipboard (state), reads what it needs, 
# and returns a dictionary to update the clipboard for the next person.

async def bob_node(state: TeamState):
    print("\n[GRAPH] Routing to Bob...")
    prompt = state["user_request"]
    
    # 1. Fetch the running blacklist from the clipboard
    rejected_list = state.get("rejected_properties", [])
    
    manager_notes = state.get("human_feedback", "").strip()
    
    # If there is feedback AND Bob has a previous draft, we are in a loop!
    if manager_notes and state.get("bob_draft"):
        print("   -> [SYSTEM] Passing human rejection feedback to Bob...")
        try:
            old_data = json.loads(state["bob_draft"])
            bad_id = old_data.get("property_id", "")
            
            # 2. Add the newly rejected house to the permanent blacklist
            if bad_id and bad_id not in rejected_list:
                rejected_list.append(bad_id)
            
            # 3. Instruct Bob to use the ENTIRE LIST array
            prompt += f"\n\nMANAGER FEEDBACK: You previously picked properties that were rejected. The manager said: '{manager_notes}'. You MUST use your semantic_property_search tool and pass this exact array {rejected_list} into the excluded_property_id parameter to find a DIFFERENT property."
        except Exception:
            pass

    raw_json_reply = await bob_agent.chat(prompt)
    print(f"   -> [BOB'S RAW OUTPUT]: {raw_json_reply}")
    
    # 4. Save BOTH the draft and the updated blacklist back to the clipboard!
    return {
        "bob_draft": raw_json_reply,
        "rejected_properties": rejected_list # <-- Updates the state for the next loop!
    }

async def nancy_node(state: TeamState):
    print("\n[GRAPH] Routing to Nancy...")
    
    # Nancy can now read exact data keys instead of parsing a paragraph!
    bob_data = json.loads(state['bob_draft'])
    prompt = f"The user asked: '{state['user_request']}'. Bob found a house that costs ${bob_data['price']}. Please do the mortgage math."
    
    reply = await nancy_agent.chat(prompt)
    return {"nancy_draft": reply, "nancy_approved": True}

async def alice_node(state: TeamState):
    print("\n[GRAPH] Routing to Alice...")
    
    # 1. Check if the human left any notes!
    manager_notes = state.get("human_feedback", "")
    
    # 2. Build a highly specific, boundary-enforcing prompt
    if manager_notes.strip():
        instruction = f"""
        The Human Manager reviewed Nancy's math and said: '{manager_notes}'. 
        If the manager's note implies rejecting the property or asking for a new one, 
        you MUST set 'is_approved' to False. 
        DO NOT use any tools to search for new properties yourself. Leave that to the Realtor. 
        Just explain the rejection in your legal_report.
        """
    else:
        instruction = "Provide a standard legal review. Set is_approved to True if the math is correct."
        
    prompt = f"Nancy calculated this: '{state['nancy_draft']}'. {instruction}"
    
    raw_json_reply = await alice_agent.chat(prompt)
    print(f"   -> [ALICE'S RAW OUTPUT]: {raw_json_reply}")
    
    alice_data = json.loads(raw_json_reply)
    
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
    # Connecting to multiple MCP servers
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
        # --- NEW: THE PAUSE BUTTON --- Human in the loop
        # 1. Initialize the save state
        memory = MemorySaver()
        
        # 2. Compile the graph with an interrupt BEFORE Alice's node
        app = builder.compile(
            checkpointer=memory,
            interrupt_before=["Alice"] 
        )

        # 5. Kick off the workflow!
        user_prompt = "I have two large dogs and need a place with a huge yard. Can you guys help me figure out what I'm looking at financially?"
        print(f"\nUSER: {user_prompt}")
        
        initial_clipboard = {
            "user_request": user_prompt,
            "bob_draft": "",
            "rejected_properties": [], # <-- FIX: Initialize the empty array here!
            "nancy_draft": "",
            "nancy_approved": False,
            "human_feedback": "",
            "final_report": "",
            "alice_approved": False
        }

        config = {"configurable": {"thread_id": "customer_123"}}

        # --- PHASE 1: RUN UNTIL PAUSE ---
        print("\n[SYSTEM] Pushing clipboard down the line...")
        # Notice we pass the config in so the memory knows where to save!
        paused_state = await app.ainvoke(initial_clipboard, config)

        # --- THE HUMAN REVIEW INTERVENTION ---
        print("\n========================================")
        print(" ⚠️ GRAPH PAUSED: HUMAN REVIEW REQUIRED ⚠️")
        print("========================================")

        # We can peek at the clipboard while the graph is asleep!
        current_clipboard = app.get_state(config).values
        print(f"Nancy's Math Draft:\n{current_clipboard.get('nancy_draft')}")
        
        # 1. Capture actual text input from the user
        print("\n[HUMAN] Type your instructions for Alice.")
        user_notes = input("        (Or just press ENTER to approve as-is): ")

        # 2. THE MAGIC: Inject the text into the sleeping graph!
        # This manually updates the 'human_feedback' variable in the database
        app.update_state(config, {"human_feedback": user_notes})

        # --- PHASE 2: RESUME THE GRAPH ---
        print("\n[SYSTEM] Resuming graph execution...")
        # To resume, we pass 'None' as the input, and use the EXACT SAME thread_id.
        # The graph will load the saved clipboard and pick up exactly where it left off.
        final_state = await app.ainvoke(None, config)

        print("\n========================================")
        print("  FINAL TEAM REPORT")
        print("========================================")
        print(final_state["final_report"])

    finally:
        await mcp_tools.disconnect()

if __name__ == "__main__":
    asyncio.run(run_graph())