import asyncio
import operator
import os
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from google import genai
from google.genai import types

# Import our decoupled Hands!
from client.property_client import ToolManager

# Initialize Gemini
client = genai.Client()

# ==========================================
# 1. THE STATE (The Assembly Line Clipboard)
# ==========================================
class TeamState(TypedDict):
    # This automatically merges new messages into the history array
    messages: Annotated[list, operator.add]

# ==========================================
# 2. THE AGENT ENGINE (The Brain + Hands logic)
# ==========================================
async def run_agent(name: str, role: str, state: TeamState, mcp_tools: ToolManager) -> str:
    """A helper function so all our agents can share the same reasoning logic."""
    print(f"[{name.upper()}] Reading clipboard and thinking...")
    
    # Grab the whole tool menu from the server
    gemini_menu = await mcp_tools.get_menu_for_gemini()
    
    # We give the agent the ENTIRE graph history so they know what happened before them
    history = state["messages"]
    
    iteration_count = 0
    while iteration_count < 3:
        config = types.GenerateContentConfig(
            system_instruction=f"You are {name}, a {role}. Read the conversation and do your specific job. Use tools if necessary.",
            tools=gemini_menu,
            temperature=0.0
        )
        
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=history,
            config=config
        )
        
        # If the agent wants to use an MCP tool
        if response.function_calls:
            iteration_count += 1
            fc = response.function_calls[0]
            print(f"   -> [{name}] Executing MCP Tool: '{fc.name}'...")
            
            raw_text = await mcp_tools.execute(fc.name, fc.args)
            
            # Temporarily append the tool result to the history so the agent can read it
            history.append(response.candidates[0].content)
            history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(name=fc.name, response={"result": raw_text})]
                )
            )
            
        # If the agent is done and just wants to talk
        elif response.text:
            return response.text

    return f"[{name}] Encountered an error."

# ==========================================
# 3. THE NODES (The Workers)
# ==========================================
# We wrap our helper function into specific LangGraph Nodes.
# We will inject the 'mcp_manager' globally when we run the graph.

async def bob_node(state: TeamState):
    reply = await run_agent(
        "Bob", 
        "Realtor. Find a property that matches the user's needs and explicitly state the price.", 
        state, 
        global_mcp_manager
    )
    return {"messages": [types.Content(role="model", parts=[types.Part.from_text(text=f"**Realtor Bob:** {reply}")])]}

async def nancy_node(state: TeamState):
    reply = await run_agent(
        "Nancy", 
        "Mortgage Broker. Read Bob's property choice and calculate the monthly payment assuming 6.5% interest over 30 years.", 
        state, 
        global_mcp_manager
    )
    return {"messages": [types.Content(role="model", parts=[types.Part.from_text(text=f"**Broker Nancy:** {reply}")])]}

async def alice_node(state: TeamState):
    reply = await run_agent(
        "Alice", 
        "Legal Reviewer. Briefly summarize the financial commitment the user is making based on Nancy's math, and add a standard legal disclaimer.", 
        state, 
        global_mcp_manager
    )
    return {"messages": [types.Content(role="model", parts=[types.Part.from_text(text=f"**Legal Alice:** {reply}")])]}

# ==========================================
# 4. ORCHESTRATION (The Factory Floor)
# ==========================================
async def main():
    print("========================================")
    print("  BOOTING LANGGRAPH MULTI-AGENT PIPELINE")
    print("========================================\n")

    # 1. Boot the shared MCP Server Connection
    global global_mcp_manager
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server", "property_server.py")
    global_mcp_manager = ToolManager(server_script_path=server_path)
    await global_mcp_manager.connect()

    try:
        # 2. Build the Graph
        builder = StateGraph(TeamState)
        
        builder.add_node("Bob", bob_node)
        builder.add_node("Nancy", nancy_node)
        builder.add_node("Alice", alice_node)
        
        # Draw the linear assembly line
        builder.add_edge(START, "Bob")
        builder.add_edge("Bob", "Nancy")
        builder.add_edge("Nancy", "Alice")
        builder.add_edge("Alice", END)
        
        app = builder.compile()

        # 3. Kick off the workflow!
        user_prompt = "I have a couple of dogs and need a place with space. Can you guys help me figure out what I'm looking at financially?"
        print(f"USER: {user_prompt}\n")
        
        initial_state = {
            "messages": [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]
        }

        # app.ainvoke() pushes the state through the entire graph asynchronously
        final_state = await app.ainvoke(initial_state)

        # 4. Print the final assembled clipboard
        print("\n========================================")
        print("  FINAL TEAM REPORT")
        print("========================================")
        for msg in final_state["messages"][1:]: # Skip the user's initial prompt
            print(msg.parts[0].text)
            print("-" * 40)

    finally:
        await global_mcp_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())