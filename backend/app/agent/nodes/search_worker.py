from __future__ import annotations

import logging
import os

from tavily import AsyncTavilyClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from langgraph.config import get_stream_writer

logger = logging.getLogger(__name__)

_tavily = AsyncTavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))


class TavilyError(Exception):
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _search(query: str) -> list[dict]:
    response = await _tavily.search(
        query=query,
        search_depth="advanced",
        max_results=6,
        include_raw_content="markdown",
        chunks_per_source=3,
    )
    return response.get("results", [])


async def search_worker(state: dict) -> dict:
    """Run a single Tavily search for one sub-query. Invoked via Send fan-out."""
    writer = get_stream_writer()
    query: str = state["sub_query"]
    parent_query: str = state.get("query", "")

    writer({
        "type": "step",
        "step": "searching",
        "message": f"Searching: \"{query}\"",
    })

    results: list[dict] = []
    try:
        raw = await _search(query)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "raw_content": r.get("raw_content", ""),
                "score": r.get("score", 0.0),
                "sub_query": query,
            }
            for r in raw
        ]
        logger.info("search_worker: query=%r found=%d", query, len(results))
        writer({
            "type": "step",
            "step": "searching",
            "message": f"Found {len(results)} results for \"{query}\"",
        })
    except Exception as exc:
        logger.warning("search_worker: query=%r error=%s", query, exc)
        writer({
            "type": "warning",
            "message": f"Search failed for \"{query}\": {exc}",
        })

    return {
        "search_results": results,
        "search_completed": 1,
    }
