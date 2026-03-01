from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agent.state import ResearchState
from app.agent.nodes.query_planner import query_planner
from app.agent.nodes.search_worker import search_worker
from app.agent.nodes.synthesizer import synthesizer, reflector


# ---------------------------------------------------------------------------
# Barrier / join node
# ---------------------------------------------------------------------------

def search_join(state: ResearchState) -> dict:
    """Self-loop barrier: waits until all search workers have reported back."""
    return {}


# ---------------------------------------------------------------------------
# Fan-out edge function
# ---------------------------------------------------------------------------

def dispatch_searches(state: ResearchState) -> list[Send]:
    """Fan out one search_worker per sub-query."""
    return [
        Send("search_worker", {"sub_query": q, "query": state["query"]})
        for q in state["sub_queries"]
    ]


# ---------------------------------------------------------------------------
# Conditional edge routers
# ---------------------------------------------------------------------------

def search_join_router(state: ResearchState) -> str:
    completed = state.get("search_completed", 0)
    expected = state.get("search_expected", 0)
    if completed >= expected and expected > 0:
        return "advance"
    return "wait"


def should_continue(state: ResearchState) -> str:
    if state.get("done", False):
        return "stop"
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    if iteration >= max_iterations:
        return "stop"
    return "loop"


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    builder = StateGraph(ResearchState)

    # Register nodes
    builder.add_node("query_planner", query_planner)
    builder.add_node("search_worker", search_worker)
    builder.add_node("search_join", search_join)
    builder.add_node("synthesizer", synthesizer)
    builder.add_node("reflector", reflector)

    # Entry
    builder.add_edge(START, "query_planner")

    # Fan-out: query_planner → N search_workers
    builder.add_conditional_edges("query_planner", dispatch_searches, ["search_worker"])

    # Fan-in: search_workers → search_join barrier → synthesizer
    builder.add_edge("search_worker", "search_join")
    builder.add_conditional_edges(
        "search_join",
        search_join_router,
        {"advance": "synthesizer", "wait": "search_join"},
    )

    # Synthesis → reflection → loop or end
    builder.add_edge("synthesizer", "reflector")
    builder.add_conditional_edges(
        "reflector",
        should_continue,
        {"loop": "query_planner", "stop": END},
    )

    return builder


# Compiled graph (singleton, imported by runner)
_graph = build_graph().compile()


def get_graph():
    return _graph
