import os
import asyncio
import inspect
import json
from google import genai
from google.genai import types

# ==========================================
# 0. API SETUP & VALIDATION
# ==========================================
if not os.environ.get("GEMINI_API_KEY"):
    print("\n[FATAL ERROR] GEMINI_API_KEY environment variable is not set!")
    print("Please set it in your terminal before running this script.")
    exit(1)

client = genai.Client()

# ==========================================
# 1. GLOBAL STATE (THE CLIPBOARD)
# ==========================================
shared_state = {
    "house": {},
    "user": {}
}

# ==========================================
# 2. TOOLS (Docstrings are CRITICAL here—the LLM reads them!)
# ==========================================
def update_state(category: str, key: str, value: str) -> str:
    """Use this to remember facts about the user or their house preferences. Category MUST be 'house' or 'user'."""
    if category in shared_state:
        shared_state[category][key] = value
        print(f"  [SYSTEM] State Updated: {category} -> {key} = {value}")
        return f"Success. {key} saved."
    return "Error: Invalid category."

def check_inventory(budget: int) -> str:
    """Use this to query the real estate database for available properties based on a maximum budget."""
    print(f"  [SYSTEM] Querying Database for budget: ${budget}...")
    if budget >= 500000:
        return "1 beautiful 3-bedroom property available in Austin, TX for $550k!"
    return "0 units available in that price range."

async def consult_sales_agent(customer_profile: str) -> str:
    """Use this to escalate the conversation to Bob, the Sales Agent, if the user wants to BUY a house."""
    print(f"\n  >>> [ROUTING] Nancy is waking up Bob the Sales Agent >>>")
    # Bob takes over!
    response = await bob.analyze_inquiry(customer_profile)
    print(f"  <<< [ROUTING] Bob finished. Handing response back to Nancy <<<\n")
    return response

# ==========================================
# 3. THE AGENT ENGINE
# ==========================================
class PropertyAgent:
    def __init__(self, name: str, role: str, prompt_rules: str, tools: list = None):
        self.name = name
        self.role = role
        self.prompt_rules = prompt_rules
        self.tools = tools or []
        self.tool_map = {tool.__name__: tool for tool in self.tools}
        self.memory = [] # Starts empty! System prompt is injected dynamically.
        
    async def analyze_inquiry(self, customer_message: str) -> str:
        # Append the user's message in the strict Gemini format
        self.memory.append(
            types.Content(role="user", parts=[types.Part.from_text(text=customer_message)])
        )
        
        iteration_count = 0
        max_iterations = 4  # THE KILL SWITCH
        
        while iteration_count < max_iterations:
            # DYNAMIC INJECTION: Give the LLM the rules and the live clipboard
            dynamic_instruction = f"You are {self.role} named {self.name}. {self.prompt_rules} Current global state clipboard: {json.dumps(shared_state)}"
            
            config = types.GenerateContentConfig(
                system_instruction=dynamic_instruction,
                tools=self.tools,
                temperature=0.0 # Keep it predictable!
            )
            
            # CALL GEMINI
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=self.memory,
                config=config
            )
            
            # Safely append the model's exact output to memory
            if response.candidates and response.candidates[0].content:
                 self.memory.append(response.candidates[0].content)
            
            # HANDLE TOOL CALLS
            if response.function_calls:
                iteration_count += 1
                fc = response.function_calls[0] # We process one tool at a time
                tool_name = fc.name
                args = fc.args
                
                print(f"[{self.name}'s Brain] -> Decided to use '{tool_name}'...")
                
                # Execute the tool safely
                tool_function = self.tool_map.get(tool_name)
                if not tool_function:
                    raw_result = f"Error: Tool {tool_name} not found."
                elif inspect.iscoroutinefunction(tool_function):
                    raw_result = await tool_function(**args)
                else:
                    raw_result = tool_function(**args)
                    
                # Return the result to the LLM as a FunctionResponse
                self.memory.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=tool_name, response={"result": raw_result})]
                    )
                )
                
            # HANDLE TEXT (Final Answer)
            elif response.text:
                return response.text
                
        return f"[SYSTEM ERROR] {self.name} exceeded {max_iterations} tool calls. Terminated to prevent infinite loop."

# ==========================================
# 4. INITIALIZATION & EXECUTION
# ==========================================

# Strict Prompt Engineering to prevent the "Shared Brain Crash"
bob_rules = "You ONLY handle sales. Use check_inventory to find homes. NEVER attempt to transfer the user."
nancy_rules = "You handle initial customer service. If the user wants to BUY, use update_state to save their budget to the 'house' category, then ALWAYS use consult_sales_agent to let Bob find the house. Formulate Bob's finding nicely for the user."

bob = PropertyAgent(name="Bob", role="Sales Agent", prompt_rules=bob_rules, tools=[check_inventory])
nancy = PropertyAgent(name="Nancy", role="Leasing Router", prompt_rules=nancy_rules, tools=[update_state, consult_sales_agent])

async def main():
    print("========================================")
    print("  INITIALIZING LIVE AI MAS ENGINE       ")
    print("========================================\n")
    
    user_query = "I'm moving to Austin next month. I want to buy a house, and my maximum budget is 600000."
    print(f"USER: \"{user_query}\"\n")
    
    final_output = await nancy.analyze_inquiry(user_query)
    
    print("\n========================================")
    print(f"FINAL LLM OUTPUT TO USER:\n{final_output}")
    print("========================================")
    print(f"FINAL SYSTEM STATE:\n{json.dumps(shared_state, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())