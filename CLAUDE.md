# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **multi-phase educational project** that progressively builds a real estate AI assistant, demonstrating increasingly sophisticated agent architectures — from basic hierarchical agents through MCP integration, RAG/vector search, LangGraph workflow orchestration, and human-in-the-loop approval flows.

## Running the Code

**Required environment variable (all phases except the mock-LLM file):**
```bash
export GEMINI_API_KEY="your_key_here"
```
Phase 4 (`phase_4.py`) validates this at startup and exits immediately if unset.

**Install dependencies** (no requirements.txt — infer from imports):
```bash
pip install google-genai mcp langgraph chromadb pydantic
```

**Run each phase from its own directory.**
MCP server paths are resolved relative to each `main.py`'s `__file__`, so running from the repo root will fail with file-not-found errors.

```bash
# Phase 1-5: Mock LLM (no API key needed)
python "Phase 1 to 5 - building Agent/Hierarchical-multi-agent.py"

# Phase 1-5: Real Gemini API (requires GEMINI_API_KEY)
python "Phase 1 to 5 - building Agent/phase_4.py"

# Phase 6: MCP intro
python "phase 6 - MCP/main.py"

# Phase 7: RAG + vector DB
python "Phase 7 - RAG and Infinite Context/main.py"
# Standalone vector DB demo:
python "Phase 7 - RAG and Infinite Context/vector_sandbox_sample.py"

# Phase 8: LangGraph workflow (production version)
python "Phase 8 - Langgraph/main_final.py"
# Standalone LangGraph basics (single node, no MCP, no tools):
python "Phase 8 - Langgraph/graph_sandbox.py"
# Simpler linear version without checkpointing:
python "Phase 8 - Langgraph/langgraph_simple_multi_agent_main.py"

# Phase 9: Human-in-the-loop (will pause and prompt for input)
python "Phase 9 -Human in the loop/main.py"

# Phase 10: Parallel fan-out/fan-in with zoning check + HITL
python "Phase 10 - Parallel/main.py"
```

## Architecture

### Phase Progression

| Phase | Key Addition | Entry Point |
|-------|-------------|-------------|
| 1–5 (mock) | Hierarchical agents, mock LLM, tool routing by hand | `Hierarchical-multi-agent.py` |
| 1–5 (real) | Same architecture wired to real Gemini API + shared state clipboard | `phase_4.py` |
| 6 | Model Context Protocol (MCP) — tools live in a subprocess server | `main.py` |
| 7 | ChromaDB vector DB + semantic property search (RAG) | `main.py` |
| 8 | LangGraph StateGraph, multi-agent pipeline, conditional routing | `main_final.py` |
| 9 | LangGraph checkpoints, graph interruption, human feedback injection | `main.py` |
| 10 | Parallel fan-out/fan-in (Bob→Nancy+Zoning→Merge→Alice), zoning tool, HITL | `main.py` |

### Standard Module Layout (Phases 6–10)

```
agent/property_agent.py       # PropertyAgent class — Gemini chat loop with memory
mcp_client/property_client.py # ToolManager — connects to MCP servers, routes tool calls
mcp_server/property_server.py # FastMCP server — defines tools (mortgage calc, inventory, search)
mcp_server/vector_db.py       # PropertyDatabase — ChromaDB + Google embeddings (Phases 7–10)
main.py                        # Entry point — wires together graph/agents/MCP
```

### Key Patterns

**Agent loop** — `PropertyAgent` maintains a `memory` list of Gemini `Content` objects that accumulates across the agent's entire graph run (not reset between `chat()` calls). An `max_iterations` guard (4) prevents infinite tool loops. Temperature is always `0.0` for deterministic output.

**MCP client/server** — The MCP server runs as a subprocess spawned by `StdioServerParameters`. `ToolManager` lists tools at runtime, converts them to Gemini function-declaration format, routes execution to the right server, and closes cleanly via `AsyncExitStack`.

**Multi-server routing (Phase 8+)** — `ToolManager` accepts a dict of `{server_name: script_path}`. It builds a `tool_routing` map at connect time so each tool call goes to the correct subprocess.

**LangGraph state machine (Phase 8+)** — `TeamState` is a TypedDict shared clipboard passed through every node. Conditional edges inspect agent output to route approval/rejection. Pydantic `response_schema` enforces JSON output.

**JSON mode (Phase 10)** — When `PropertyAgent` is constructed with `response_schema=SomePydanticModel`, it sets `response_mime_type = "application/json"` and `response_schema = SomePydanticModel` on the Gemini config, forcing the model to emit valid JSON matching the schema.

**Human-in-the-loop (Phase 9+)** — `MemorySaver` provides thread-based persistence. `interrupt_before=["Alice"]` pauses the graph before Alice. The main script calls `app.get_state()` to inspect mid-graph values, `app.update_state()` to inject `human_feedback`, then `app.ainvoke(None, config)` to resume. Rejected properties accumulate in `rejected_properties` to prevent re-recommendation.

**RAG (Phase 7+)** — `PropertyDatabase` wraps ChromaDB with Google's embedding function. The vector DB is lazy-loaded on the first `semantic_property_search()` call. Queries return the nearest document by cosine distance along with structured metadata (price, type).

### Phase 10 — Parallel Fan-Out / Fan-In

Phase 10 extends Phase 9 by splitting the sequential Bob→Nancy chain into a **parallel** Bob→(Nancy ∥ Zoning)→Merge→Alice pipeline.

#### Graph Topology

```
START → Bob ──┬──→ Nancy (mortgage broker)  ──┐
              │                                ├──→ Merge ──→ [HITL pause] ──→ Alice ──→ END
              └──→ Zoning (zoning officer)   ──┘                                  │
                                                                                   └── (reject) → Bob
```

#### Agents

| Agent | Role | Tools | Output Schema |
|-------|------|-------|---------------|
| Bob | Senior Realtor | `semantic_property_search` | `BobOutput` (property_id, price, type, description_summary) |
| Nancy | Mortgage Broker | `calculate_mortgage` | plain text |
| Zoning | Municipal Zoning Officer | `check_zoning` | `ZoningOutput` (zone_name, is_compliant, zoning_summary) |
| Merge | Pure Python node (no LLM) | — | structured brief string |
| Alice | Legal Reviewer | none | `AliceOutput` (is_approved, legal_report) |

#### New MCP Tool — `check_zoning(property_id, property_type)`

Added to `mcp_server/property_server.py`. Looks up a mock zoning database (4 listings) and returns zone classification, permitted uses, restrictions, and compliance verdict. `listing_3` is industrial and intentionally non-compliant to exercise the rejection path.

#### Key Patterns (new in Phase 10)

**Parallel fan-out/fan-in** — `graph.add_edge("Bob", "Nancy")` and `graph.add_edge("Bob", "Zoning")` fire both nodes concurrently. LangGraph holds Merge until both upstream nodes complete; no explicit synchronization code needed.

**Merge node** — A plain Python function (no Gemini call) that concatenates Nancy's and Zoning's outputs into a single `merge_summary` string for Alice to review.

**`TeamState` fields** — `bob_draft`, `nancy_draft`, `zoning_draft`, `merge_summary`, `human_feedback`, `final_report`, `alice_approved`, `rejected_properties`.

**Rejection loop** — `quality_control_router()` returns `"Bob"` when `alice_approved == False`; the rejected `property_id` is appended to `rejected_properties` so `semantic_property_search` skips it on the next iteration.

### LLM Models Used

| Phase | Model | Notes |
|-------|-------|-------|
| 1–5 | `gemini-2.5-flash` | Synchronous `client.models.generate_content` |
| 6–7 | `gemini-2.5-flash` | Async via `google-genai` SDK |
| 8–9 | `gemini-2.5-flash-lite` | Lighter model sufficient for structured routing |
| 10 | `gemini-3.1-flash-lite-preview` | Set in `agent/property_agent.py`; update if the model ID changes |
