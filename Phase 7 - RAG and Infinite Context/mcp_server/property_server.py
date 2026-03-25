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
def semantic_property_search(search_query: str) -> str:
    """Use this to search the real estate database for homes based on natural language preferences."""
    global db_instance
    print("[SERVER LOG] Attempt to boot the database server", file=sys.stderr)
    # --- LAZY LOADING ---
    # If the database hasn't been turned on yet, boot it up now!
    if db_instance is None:
        print("[SERVER LOG] First search detected! Booting Vector DB...", file=sys.stderr)
        db_instance = PropertyDatabase()
        print("[SERVER LOG] Vector DB populated and ready.", file=sys.stderr)
    # --------------------

    print(f"[SERVER LOG] Executing semantic search for: '{search_query}'...", file=sys.stderr)
    return db_instance.search_properties(search_query)

if __name__ == "__main__":
    # The server runs immediately and silently, ready to handshake!
    mcp.run()