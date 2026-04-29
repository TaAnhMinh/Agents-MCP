import sys
import warnings

warnings.filterwarnings("ignore")

from mcp.server.fastmcp import FastMCP
from vector_db import PropertyDatabase

mcp = FastMCP("PropertyServer")

db_instance = None


# ==========================================
# TOOL 1: Mortgage Calculator (unchanged)
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


# ==========================================
# TOOL 2: Semantic Property Search (unchanged)
# ==========================================

@mcp.tool()
def semantic_property_search(search_query: str, excluded_property_id: list[str]) -> str:
    """Use this to search the real estate database. Pass an excluded_property_id to skip a specific house."""
    global db_instance
    if db_instance is None:
        db_instance = PropertyDatabase()

    print(f"[SERVER LOG] Executing search (Excluding: '{excluded_property_id}')...", file=sys.stderr)
    return db_instance.search_properties(search_query, excluded_property_id)


# ==========================================
# TOOL 3: Zoning Checker (NEW for Phase 10)
#
# Simulates a municipal zoning database lookup.
# Returns the zone classification, permitted uses,
# key restrictions, and a compliance verdict for
# the given property ID.
# ==========================================

# Mock zoning database keyed by listing ID.
# Each entry mirrors the listings in vector_db.py so the
# Zoning Agent can make a meaningful compliance ruling.
_ZONING_DATABASE = {
    "listing_1": {
        "zone":           "Downtown Commercial (DC-5)",
        "permitted_uses": ["high-rise residential condo", "retail", "office"],
        "restrictions":   "No single-family detached homes. Noise ordinance after 11 PM.",
        "is_compliant":   True,
    },
    "listing_2": {
        "zone":           "Residential Low-Density (R-2)",
        "permitted_uses": ["single-family home", "duplex", "home-based business"],
        "restrictions":   "Max building height 2 storeys. No commercial signage.",
        "is_compliant":   True,
    },
    # The fixer-upper sits in an industrial zone — residential use is NOT permitted
    # without a variance. This is the interesting "fail" case for the Zoning Agent.
    "listing_3": {
        "zone":           "Industrial Mixed-Use (M-1)",
        "permitted_uses": ["light manufacturing", "warehouse", "auto-repair shop"],
        "restrictions":   "Residential occupancy PROHIBITED without City Council variance. "
                          "Environmental hazard assessment required before any renovation.",
        "is_compliant":   False,
    },
    "listing_4": {
        "zone":           "Waterfront Estate (WE-1)",
        "permitted_uses": ["single-family estate", "private dock", "guest house"],
        "restrictions":   "Coastal Commission permit required. Property cannot be subdivided. "
                          "Annual environmental levy of $12,000 applies.",
        "is_compliant":   True,
    },
}


@mcp.tool()
def check_zoning(property_id: str, property_type: str) -> str:
    """
    Check local zoning regulations for a property.
    Returns zone classification, permitted uses, key restrictions,
    and whether the property is zoning-compliant for residential use.
    """
    print(
        f"[SERVER LOG] Executing check_zoning for property '{property_id}' (type: {property_type})...",
        file=sys.stderr,
    )

    record = _ZONING_DATABASE.get(property_id)
    if not record:
        return (
            f"No zoning record found for property ID '{property_id}'. "
            "Manual municipal lookup required."
        )

    status = "COMPLIANT" if record["is_compliant"] else "NON-COMPLIANT — residential use may be prohibited"
    permitted_str = ", ".join(record["permitted_uses"])

    return (
        f"Zoning Report for {property_id} (type: {property_type}):\n"
        f"  Zone Classification : {record['zone']}\n"
        f"  Permitted Uses      : {permitted_str}\n"
        f"  Key Restrictions    : {record['restrictions']}\n"
        f"  Compliance Status   : {status}"
    )


if __name__ == "__main__":
    mcp.run()
