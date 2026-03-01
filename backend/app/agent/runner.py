from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from langgraph.errors import GraphRecursionError

from app.agent.graph import get_graph

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 3
RECURSION_LIMIT = 100


async def run_research_stream(
    query: str,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    queue: asyncio.Queue | None = None,
) -> dict | None:
    """
    Run the research agent and stream progress events to an asyncio.Queue.

    Each event pushed to the queue is a plain dict matching the SSE event schema:
      { "type": "step"|"warning"|"complete"|"error", ... }

    Returns the final report dict (also sent as the "complete" event).
    """
    graph = get_graph()

    initial_state = {
        "query": query,
        "sub_queries": [],
        "search_results": [],
        "search_expected": 0,
        "search_completed": 0,
        "answer_draft": "",
        "citations": [],
        "report": None,
        "synthesis_error": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "done": False,
    }

    config = {"recursion_limit": RECURSION_LIMIT}

    final_report: dict | None = None
    synthesis_error: str | None = None

    def _emit(event: dict) -> None:
        if queue is not None:
            queue.put_nowait(event)

    try:
        async for stream_event in graph.astream(
            initial_state,
            config=config,
            stream_mode=["custom", "updates"],
        ):
            # stream_event is a tuple: (mode, data)
            mode, data = stream_event if isinstance(stream_event, tuple) else ("updates", stream_event)

            if mode == "custom":
                # Events emitted by get_stream_writer() inside nodes
                _emit(data)

            elif mode == "updates":
                # State delta after a node completes — extract final report if present
                for _node_name, node_update in data.items():
                    if isinstance(node_update, dict):
                        if node_update.get("report"):
                            final_report = node_update["report"]
                        if node_update.get("synthesis_error"):
                            synthesis_error = node_update["synthesis_error"]

        # Research complete
        if final_report:
            _emit({
                "type": "complete",
                "report": final_report,
                "degraded": bool(synthesis_error),
                "warning": synthesis_error,
            })
        else:
            _emit({
                "type": "error",
                "message": "Agent completed but produced no report.",
            })

    except GraphRecursionError:
        logger.error("run_research_stream: recursion limit hit for query=%r", query)
        _emit({
            "type": "error",
            "message": "Research agent hit the recursion limit. Partial results may be available.",
        })
    except Exception as exc:
        logger.exception("run_research_stream: unexpected error for query=%r", query)
        _emit({"type": "error", "message": str(exc)})

    return final_report


async def stream_to_sse(
    query: str,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncIterator[str]:
    """
    Async generator that yields SSE-formatted strings.
    Used directly by the FastAPI StreamingResponse.
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()

    # Run the agent as a background task so we can yield from the queue concurrently
    agent_task = asyncio.create_task(
        run_research_stream(query, max_iterations=max_iterations, queue=queue)
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                # Send a keepalive comment so the connection doesn't drop
                yield ": keepalive\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            if event.get("type") in ("complete", "error"):
                break
    finally:
        agent_task.cancel()
        try:
            await agent_task
        except (asyncio.CancelledError, Exception):
            pass
