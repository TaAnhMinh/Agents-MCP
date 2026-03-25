from mcp.server.fastmcp import FastMCP

#MCP SERVER

# 1. Initialize the server with a name
mcp = FastMCP("PropertyServer")

# 2. Use the @mcp.tool() decorator. 
# This automatically converts the function and its docstring into an MCP-compliant JSON schema!
@mcp.tool()
def calculate_mortgage(principal: float, interest_rate: float, years: int) -> str:
    """Calculates the estimated monthly mortgage payment for a property."""
    print(f"[SERVER LOG] Calculating mortgage for ${principal}...")
    
    # Standard mortgage math
    monthly_rate = interest_rate / 100 / 12
    num_payments = years * 12
    if monthly_rate == 0:
        payment = principal / num_payments
    else:
        payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
        
    return f"The estimated monthly payment is ${round(payment, 2)}"

@mcp.tool()
def check_external_inventory(budget: int) -> str:
    """Queries the external real estate database for homes under budget. Simulating real db"""
    print(f"[SERVER LOG] Checking database for budget: ${budget}...")
    if budget >= 500000:
        return "1 beautiful property found in the external database!"
    return "0 units available."

if __name__ == "__main__":
    print("Starting PropertyServer on standard input/output...")
    # 3. Run the server! It will listen for standardized JSON-RPC messages.
    mcp.run()