import asyncio
import inspect

# --- The Mock LLM API (Simplified for simulation) ---
async def mock_llm_call(messages: list) -> str | dict:
    # 1. Read the agent's identity from the very first message
    system_prompt = messages[0]["content"]
    # 2. Read the latest thing added to the memory
    latest_message = messages[-1]["content"]
    
    # Check if the last message was from the user, meaning the LLM might need to use a tool
    if messages[-1]["role"] == "user":
        
        # ==========================================
        # TASK 1: Nancy's Logic (Leasing Assistant)
        # ==========================================
        # Write an 'if' statement checking if "Leasing" is in the system_prompt 
        # AND "buy" is in the latest_message.lower().
        # If true, return: {"tool_call": "consult_sales_agent", "arguments": {"customer_profile": latest_message}}
        if "Leasing" in system_prompt and "buy" in latest_message.lower():
            return {"tool_call": "consult_sales_agent", "arguments": {"customer_profile": latest_message}}
        
        
        # ==========================================
        # TASK 2: Bob's Logic (Sales Agent)
        # ==========================================
        # Write an 'elif' statement checking if "Sales" is in the system_prompt 
        # AND "buy" is in the latest_message.lower().
        # If true, return: {"tool_call": "check_inventory", "arguments": {"budget": 500000}}
        elif "Sales" in system_prompt and "buy" in latest_message.lower():
            return {"tool_call": "check_inventory", "arguments": {"budget": 500000}}
            
    # ==========================================
    # TASK 3: The Final Text Response (Already completed for you)
    # ==========================================
    # If the last message wasn't from the user (e.g., it was a tool result), 
    # generate the final text string to speak to the customer.
    if "Sales" in system_prompt:
        return f"Hi, I'm Bob. Based on my search: {latest_message}"
    else:
        return f"Hi, I'm Nancy. My sales team found this: {latest_message}"
    

# --- The Agent Engine ---
class PropertyAgent:
    def __init__(self, name: str, role: str, tools: list = None):
        self.name = name
        self.role = role
        self.tools = tools or []
        self.tool_map = {tool.__name__: tool for tool in self.tools}
        self.system_prompt = f"You are a {self.role} named {self.name}."
        self.memory = [{"role": "system", "content": self.system_prompt}]
        
    async def analyze_inquiry(self, customer_message: str) -> str:
        self.memory.append({"role": "user", "content": customer_message})
        response = await mock_llm_call(self.memory)
        
        if isinstance(response, dict):
            tool_name = response["tool_call"]
            args = response["arguments"]
            tool_function = self.tool_map[tool_name]
            
            # Check if the tool is async (e.g., another agent)
            if inspect.iscoroutinefunction(tool_function):
                tool_response = await tool_function(**args)
            else:
                tool_response = tool_function(**args)
                
            self.memory.append({"role": "tool", "content": f"{tool_name} returned: {tool_response}"})
            # Second call to LLM to process tool results
            response = await mock_llm_call(self.memory)
            
        self.memory.append({"role": "assistant", "content": response})
        return response

# --- Tools ---
def check_inventory(budget: int) -> str:
    return "1 unit available" if budget >= 500000 else "0 units available"

async def consult_sales_agent(customer_profile: str) -> str:
    print(f"\n[SYSTEM] Nancy is handing off to Bob...")
    # Bob is instantiated globally for this simulation
    response = await bob.analyze_inquiry(customer_profile)
    return response

# --- Initialization ---
bob = PropertyAgent(name="Bob", role="Sales Agent", tools=[check_inventory])
nancy = PropertyAgent(name="Nancy", role="Leasing Assistant", tools=[consult_sales_agent])

if __name__ == "__main__":
    async def main():
        result = await nancy.analyze_inquiry("I have a $500k budget and I want to buy a house.")
        print(f"\nFinal Response to Customer: {result}")

    asyncio.run(main())
