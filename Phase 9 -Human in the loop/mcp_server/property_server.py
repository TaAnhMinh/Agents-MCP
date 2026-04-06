import sys
import warnings

# Keep the silencer to suppress legacy library warnings!
warnings.filterwarnings("ignore")

from mcp.server.fastmcp import FastMCP
from vector_db import PropertyDatabase 

# 1. INITIALIZE SERVER
mcp = FastMCP("PropertyServer")

# We create an empty placeholder for the database. 
# We DO NOT boot it up here anymore!
db_instance = None 

# ==========================================
# 2. THE TOOLS (The Menu)
# ==========================================

@mcp.tool()
def calculate_mortgage(principal: float, interest_rate: float, years: int) -> str:
    """Calculates the estimated monthly mortgage payment for a property."""
    print(f"[SERVER LOG] Executing calculate_mortgage for ${principal}...", file=sys.stderr)
    monthly_rate = interest_rate / 100 / 12
    num_payments = years * 12
    if monthly_rate == 0:
        payment = principal / num_payments
    else:
        payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    return f"The estimated monthly payment is ${round(payment, 2)}"

@mcp.tool()
def semantic_property_search(search_query: str, excluded_property_id: list[str]) -> str:
    """Use this to search the real estate database. Pass an excluded_property_id to skip a specific house."""
    global db_instance
    if db_instance is None:
        db_instance = PropertyDatabase()

    print(f"[SERVER LOG] Executing search (Excluding: '{excluded_property_id}')...", file=sys.stderr)
    return db_instance.search_properties(search_query, excluded_property_id)

if __name__ == "__main__":
    # The server runs immediately and silently, ready to handshake!
    mcp.run()