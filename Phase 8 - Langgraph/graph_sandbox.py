import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from google import genai
from google.genai import types

# Initialize Gemini
client = genai.Client()

# ==========================================
# 1. DEFINE THE STATE (The Clipboard)
# ==========================================
class AgentState(TypedDict):
    # We tell LangGraph: "Whenever a Node returns a new message, 
    # use operator.add to append it to the list, don't overwrite the old ones!"
    messages: Annotated[list, operator.add]

# ==========================================
# 2. DEFINE THE NODES (The Workers)
# ==========================================
def bob_node(state: AgentState):
    print("   -> [NODE: BOB] Reading the clipboard and thinking...")
    
    # 1. Bob reads the entire conversation history from the State
    history = state["messages"]
    
    # 2. Bob generates a response
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction="You are Bob, a friendly real estate agent."
        )
    )
    
    # 3. Bob writes his new response back onto the clipboard
    new_message = response.candidates[0].content
    return {"messages": [new_message]}

# ==========================================
# 3. BUILD THE GRAPH (The Conveyor Belt)
# ==========================================
print("1. Assembling the Graph Engine...")
graph_builder = StateGraph(AgentState)

# Add our worker to the factory floor
graph_builder.add_node("bob_worker", bob_node)

# Draw the lines connecting everything
graph_builder.add_edge(START, "bob_worker") # When the graph starts, send the clipboard to Bob
graph_builder.add_edge("bob_worker", END)   # When Bob is done, end the process

# Compile it into a runnable engine
app = graph_builder.compile()

# ==========================================
# 4. RUN THE GRAPH
# ==========================================
if __name__ == "__main__":
    print("2. Starting the conversation...\n")
    
    user_input = "Hi! My name is Alex and I want to buy a house."
    print(f"USER: {user_input}")
    
    # Create the initial clipboard with the user's first message
    initial_clipboard = {
        "messages": [types.Content(role="user", parts=[types.Part.from_text(text=user_input)])]
    }
    
    # Send the clipboard down the assembly line!
    # app.invoke() automatically passes the State through the graph
    final_state = app.invoke(initial_clipboard)
    
    # Read the final state of the clipboard
    final_reply = final_state["messages"][-1].parts[0].text
    print(f"\nBOB: {final_reply}")