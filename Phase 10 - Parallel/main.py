"""
Phase 10 — Parallel Fan-out / Fan-in with Human-in-the-Loop
============================================================

Graph topology (new vs Phase 9):

    Phase 9 (sequential):
        START → Bob → Nancy → Alice → END
                         ↑_______↓  (rejection loop)

    Phase 10 (parallel fan-out / fan-in):

                        ┌──► Nancy  ──┐
        START → Bob ────┤   (finance)  ├──► Merge → Alice → END
                        └──► Zoning ──┘   (fan-in)    ↑
                           (zoning law)               │
                                 ↑______ Bob ◄─────────┘
                                         (rejection loop — Bob fans out again)

Key LangGraph concepts demonstrated:
  • Fan-out  : a single edge source (Bob) has TWO outgoing edges.
                LangGraph fires both destination nodes CONCURRENTLY.
  • Fan-in   : two nodes (Nancy, Zoning) both have edges to Merge.
                LangGraph waits for ALL upstream nodes before running Merge.
  • Merge    : pure-Python node — no LLM. Just stitches the two parallel
                outputs into one structured brief for Alice.
  • HITL     : graph pauses before Alice so a human can review the merged
                summary and inject feedback before final approval.
"""

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
# 1. PYDANTIC OUTPUT SCHEMAS
#    Each schema locks an agent's output into
#    a machine-readable JSON structure.
# ==========================================

class BobOutput(BaseModel):
    property_id: str   = Field(description="The ID of the property found")
    price:       float = Field(description="The exact price of the property as a number")
    property_type: str = Field(description="The type of property, e.g. condo, house, mansion")
    description_summary: str = Field(description="A strict 1-sentence summary of the property")


class ZoningOutput(BaseModel):
    """
    Structured verdict produced by the Zoning Agent.
    is_compliant = False means Alice will likely reject the property,
    even if Nancy's mortgage math is fine.
    """
    property_id:    str  = Field(description="The property ID that was checked")
    zone_name:      str  = Field(description="The official zone classification name")
    is_compliant:   bool = Field(description="True if residential use is permitted in this zone")
    zoning_summary: str  = Field(description="1-2 sentence plain-English summary of the zoning findings")


class AliceOutput(BaseModel):
    is_approved:  bool = Field(
        description=(
            "True only if: Nancy's mortgage math is correct AND the property is "
            "zoning-compliant AND the human manager approves. False otherwise."
        )
    )
    legal_report: str = Field(
        description=(
            "Final legal summary covering both financial feasibility and zoning "
            "compliance, OR a clear explanation of why the property was rejected."
        )
    )


# ==========================================
# 2. SHARED STATE  (The Clipboard)
#    Every node reads from and writes to this
#    TypedDict.  Fields are added compared to
#    Phase 9 to accommodate the parallel tracks.
# ==========================================

class TeamState(TypedDict):
    user_request:        str        # Original user query — never mutated
    bob_draft:           str        # Bob's JSON output (BobOutput)
    rejected_properties: list[str]  # Permanent blacklist, grows on rejection
    nancy_draft:         str        # Nancy's mortgage analysis text
    zoning_draft:        str        # Zoning Agent's JSON output (ZoningOutput)
    merge_summary:       str        # Merged brief built by Merge node for Alice
    human_feedback:      str        # Injected by the human during HITL pause
    final_report:        str        # Alice's written legal verdict
    alice_approved:      bool       # True → done; False → loop back to Bob


# ==========================================
# 3. NODE DEFINITIONS
# ==========================================

# ---- Bob (Realtor) -----------------------------------------------
# Unchanged role: find a property.
# When looping after a rejection, Bob reads the accumulated blacklist
# and the human's feedback so he never re-suggests a rejected listing.
# ------------------------------------------------------------------
async def bob_node(state: TeamState):
    print("\n[GRAPH] ► Routing to Bob (Realtor)...")

    prompt        = state["user_request"]
    rejected_list = state.get("rejected_properties", [])
    manager_notes = state.get("human_feedback", "").strip()

    # Are we in a retry loop?  Human feedback + existing draft = yes.
    if manager_notes and state.get("bob_draft"):
        print("   -> [SYSTEM] Re-running Bob with rejection feedback...")
        try:
            old_data = json.loads(state["bob_draft"])
            bad_id   = old_data.get("property_id", "")

            if bad_id and bad_id not in rejected_list:
                rejected_list.append(bad_id)

            prompt += (
                f"\n\nMANAGER FEEDBACK: The previous property was rejected. "
                f"The manager said: '{manager_notes}'. "
                f"You MUST call semantic_property_search and pass this exact array "
                f"{rejected_list} into excluded_property_id to find a DIFFERENT property."
            )
        except Exception:
            pass

    raw_json_reply = await bob_agent.chat(prompt)
    print(f"   -> [BOB OUTPUT]: {raw_json_reply}")

    return {
        "bob_draft":           raw_json_reply,
        "rejected_properties": rejected_list,
    }


# ---- Nancy (Mortgage Broker) — FAN-OUT TRACK 1 -------------------
# Reads Bob's output and runs mortgage calculations.
# Fires concurrently with Zoning after Bob completes.
# ------------------------------------------------------------------
async def nancy_node(state: TeamState):
    print("\n[GRAPH] ► Routing to Nancy (Mortgage Broker)  [parallel track 1]...")

    bob_data = json.loads(state["bob_draft"])
    prompt   = (
        f"The user asked: '{state['user_request']}'. "
        f"Bob found a {bob_data['property_type']} that costs ${bob_data['price']}. "
        f"Please calculate the monthly mortgage payment, estimate the down payment "
        f"at 20%, and give a brief affordability assessment."
    )

    reply = await nancy_agent.chat(prompt)
    print(f"   -> [NANCY OUTPUT]: {reply[:120]}...")
    return {"nancy_draft": reply}


# ---- Zoning Agent — FAN-OUT TRACK 2 ------------------------------
# Reads Bob's output and checks zoning compliance.
# Fires concurrently with Nancy after Bob completes.
# This is the NEW agent added in Phase 10.
# ------------------------------------------------------------------
async def zoning_node(state: TeamState):
    print("\n[GRAPH] ► Routing to Zoning Agent            [parallel track 2]...")

    bob_data = json.loads(state["bob_draft"])
    prompt   = (
        f"Please check the local zoning regulations for property ID "
        f"'{bob_data['property_id']}' which is a '{bob_data['property_type']}'. "
        f"Use the check_zoning tool and then give your compliance verdict."
    )

    raw_json_reply = await zoning_agent.chat(prompt)
    print(f"   -> [ZONING OUTPUT]: {raw_json_reply}")
    return {"zoning_draft": raw_json_reply}


# ---- Merge Node (Fan-in) -----------------------------------------
# This is a pure-Python node — no LLM call needed.
# LangGraph guarantees it only runs AFTER BOTH Nancy and Zoning
# have finished writing their results to the state.
# Its only job: stitch the two parallel outputs into one clean
# summary brief for Alice.
# ------------------------------------------------------------------
async def merge_node(state: TeamState):
    print("\n[GRAPH] ► Running Merge node (fan-in — waiting for both tracks)...")

    bob_data = json.loads(state["bob_draft"])

    # Parse the ZoningOutput JSON so we can highlight compliance status
    try:
        zoning_data    = json.loads(state["zoning_draft"])
        zoning_status  = "✅ COMPLIANT" if zoning_data.get("is_compliant") else "❌ NON-COMPLIANT"
        zoning_detail  = zoning_data.get("zoning_summary", state["zoning_draft"])
        zone_name      = zoning_data.get("zone_name", "Unknown")
    except Exception:
        # If JSON parse fails, fall back to raw text
        zoning_status = "⚠️ UNKNOWN"
        zoning_detail = state["zoning_draft"]
        zone_name     = "Unknown"

    # Build the unified brief Alice will read
    merge_summary = (
        f"=== PROPERTY BRIEF FOR LEGAL REVIEW ===\n\n"
        f"Property   : {bob_data.get('property_id')} ({bob_data.get('property_type')})\n"
        f"Price      : ${bob_data.get('price'):,.0f}\n"
        f"Description: {bob_data.get('description_summary')}\n\n"
        f"--- TRACK 1: FINANCIAL ANALYSIS (Nancy) ---\n"
        f"{state['nancy_draft']}\n\n"
        f"--- TRACK 2: ZONING ANALYSIS (Zoning Agent) ---\n"
        f"Zone       : {zone_name}\n"
        f"Status     : {zoning_status}\n"
        f"Detail     : {zoning_detail}"
    )

    print(f"   -> [MERGE SUMMARY BUILT — {len(merge_summary)} chars]")
    return {"merge_summary": merge_summary}


# ---- Alice (Legal Reviewer) --------------------------------------
# Reads the merged brief (not just Nancy's draft like in Phase 9).
# HITL pause happens BEFORE this node, so the human can read the
# merged summary and inject feedback before Alice renders her verdict.
# ------------------------------------------------------------------
async def alice_node(state: TeamState):
    print("\n[GRAPH] ► Routing to Alice (Legal Reviewer)...")

    manager_notes = state.get("human_feedback", "").strip()

    if manager_notes:
        instruction = (
            f"The Human Manager reviewed the team's findings and said: '{manager_notes}'. "
            f"If the manager implies rejecting this property, set 'is_approved' to False "
            f"and explain the rejection clearly in your legal_report. "
            f"DO NOT search for new properties yourself."
        )
    else:
        instruction = (
            "Provide a standard legal review. "
            "Approve only if the mortgage math is reasonable AND the property is zoning-compliant."
        )

    prompt = f"{state['merge_summary']}\n\n{instruction}"

    raw_json_reply = await alice_agent.chat(prompt)
    print(f"   -> [ALICE OUTPUT]: {raw_json_reply}")

    alice_data = json.loads(raw_json_reply)
    return {
        "final_report":   alice_data["legal_report"],
        "alice_approved": alice_data["is_approved"],
    }


# ==========================================
# 4. ROUTING FUNCTIONS
# ==========================================

def quality_control_router(state: TeamState):
    """After Alice: end on approval, loop back to Bob on rejection."""
    if state["alice_approved"]:
        return END
    else:
        print("\n[ROUTER] Alice rejected. Looping back to Bob for a new property...")
        return "Bob"


# ==========================================
# 5. GRAPH ASSEMBLY & EXECUTION
# ==========================================

async def run_graph():
    print("=" * 50)
    print("  PHASE 10 — PARALLEL FAN-OUT / FAN-IN MAS  ")
    print("=" * 50)

    base_dir    = os.path.dirname(os.path.abspath(__file__))
    server_fleet = {
        "property": os.path.join(base_dir, "mcp_server", "property_server.py"),
    }
    mcp_tools = ToolManager(server_scripts=server_fleet)

    try:
        await mcp_tools.connect()

        # Instantiate agents globally so node functions can reach them
        global bob_agent, nancy_agent, zoning_agent, alice_agent

        bob_agent = PropertyAgent(
            name="Bob",
            role=(
                "Senior Real Estate Realtor. Your job is to find properties matching "
                "the user's needs using your search tool. Do NOT do mortgage math or "
                "legal reviews."
            ),
            tool_manager=mcp_tools,
            response_schema=BobOutput,
        )

        nancy_agent = PropertyAgent(
            name="Nancy",
            role=(
                "Mortgage Broker. Your job is to perform financial calculations for a "
                "given property price using your mortgage calculator tool. Do NOT search "
                "for listings or give legal advice."
            ),
            tool_manager=mcp_tools,
        )

        # NEW: Zoning Agent — runs in parallel with Nancy
        zoning_agent = PropertyAgent(
            name="Zoning",
            role=(
                "Municipal Zoning Compliance Officer. Your job is to check local zoning "
                "regulations for a given property using your check_zoning tool and report "
                "whether residential use is permitted. Do NOT search for new listings or "
                "perform financial calculations."
            ),
            tool_manager=mcp_tools,
            response_schema=ZoningOutput,
        )

        alice_agent = PropertyAgent(
            name="Alice",
            role=(
                "Legal Reviewer. Your job is to approve or reject the team's combined "
                "financial and zoning findings. You are strictly forbidden from using "
                "any tools yourself."
            ),
            tool_manager=mcp_tools,
            response_schema=AliceOutput,
        )

        # --------------------------------------------------
        # Build the graph
        # --------------------------------------------------
        print("\n[GRAPH] Assembling the parallel pipeline...")
        builder = StateGraph(TeamState)

        # Register every node
        builder.add_node("Bob",    bob_node)
        builder.add_node("Nancy",  nancy_node)
        builder.add_node("Zoning", zoning_node)
        builder.add_node("Merge",  merge_node)
        builder.add_node("Alice",  alice_node)

        # START → Bob
        builder.add_edge(START, "Bob")

        # FAN-OUT: Bob's output is sent to BOTH Nancy and Zoning simultaneously.
        # LangGraph fires these two nodes concurrently — neither waits for the other.
        builder.add_edge("Bob", "Nancy")   # parallel track 1
        builder.add_edge("Bob", "Zoning")  # parallel track 2

        # FAN-IN: LangGraph only runs Merge once BOTH Nancy AND Zoning have finished.
        # This is the synchronisation barrier — no data is lost.
        builder.add_edge("Nancy",  "Merge")
        builder.add_edge("Zoning", "Merge")

        # Merge hands control to Alice (HITL interrupt fires here)
        builder.add_edge("Merge", "Alice")

        # Alice either ends the run or loops the whole pipeline back to Bob
        builder.add_conditional_edges("Alice", quality_control_router)

        # Compile with MemorySaver so the graph state survives the HITL pause
        memory = MemorySaver()
        app    = builder.compile(
            checkpointer=memory,
            interrupt_before=["Alice"],   # ← HITL: pause before Alice every time
        )

        # --------------------------------------------------
        # Kick off the workflow
        # --------------------------------------------------
        user_prompt = (
            "I have two large dogs and need a place with a huge yard. "
            "Can you guys help me figure out what I'm looking at financially?"
        )
        print(f"\nUSER: {user_prompt}")

        initial_state = {
            "user_request":        user_prompt,
            "bob_draft":           "",
            "rejected_properties": [],
            "nancy_draft":         "",
            "zoning_draft":        "",
            "merge_summary":       "",
            "human_feedback":      "",
            "final_report":        "",
            "alice_approved":      False,
        }

        config = {"configurable": {"thread_id": "customer_123"}}

        # --- PHASE 1: Run until HITL pause (before Alice) ---
        print("\n[SYSTEM] Starting graph — Bob will fan out to Nancy + Zoning in parallel...")
        await app.ainvoke(initial_state, config)

        # --- HUMAN REVIEW WINDOW ---
        print("\n" + "=" * 50)
        print("  ⚠️  GRAPH PAUSED — HUMAN REVIEW REQUIRED  ")
        print("=" * 50)

        # Show the human the full merged brief that Alice is about to receive
        current_state = app.get_state(config).values
        print("\n📋 MERGED BRIEF (what Alice will review):")
        print(current_state.get("merge_summary", "(empty)"))

        print("\n[HUMAN] Type your instructions for Alice.")
        user_notes = input("        (Press ENTER to approve as-is): ").strip()

        # Inject human feedback into the sleeping graph's state
        app.update_state(config, {"human_feedback": user_notes})

        # --- PHASE 2: Resume from Alice ---
        print("\n[SYSTEM] Resuming graph — handing merged brief to Alice...")
        final_state = await app.ainvoke(None, config)

        print("\n" + "=" * 50)
        print("  FINAL LEGAL REPORT")
        print("=" * 50)
        print(final_state["final_report"])

    finally:
        await mcp_tools.disconnect()


if __name__ == "__main__":
    asyncio.run(run_graph())
