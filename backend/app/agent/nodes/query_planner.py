from __future__ import annotations

import json
import logging
import os

from jinja2 import Environment, FileSystemLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.config import get_stream_writer

from app.agent.state import ResearchState

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../../prompts")
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
)


async def query_planner(state: ResearchState) -> dict:
    """Decompose the user query into focused sub-questions for parallel search."""
    writer = get_stream_writer()

    iteration = state.get("iteration", 0)
    previous_queries = state.get("sub_queries", [])

    writer({
        "type": "step",
        "step": "planning",
        "message": f"Planning research strategy (iteration {iteration + 1})...",
        "iteration": iteration + 1,
    })

    template = _jinja_env.get_template("query_decomposition.j2")
    prompt = template.render(
        query=state["query"],
        iteration=iteration,
        previous_queries=previous_queries,
        num_queries=4,
    )

    response = await _llm.ainvoke(prompt)
    content = response.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    parsed = json.loads(content)
    sub_queries: list[str] = parsed["queries"]

    writer({
        "type": "step",
        "step": "planning",
        "message": f"Generated {len(sub_queries)} search queries",
        "queries": sub_queries,
        "iteration": iteration + 1,
    })

    logger.info("query_planner: iteration=%d queries=%s", iteration + 1, sub_queries)

    return {
        "sub_queries": sub_queries,
        "search_results": [],
        "search_expected": len(sub_queries),
        "search_completed": 0,
        "iteration": iteration + 1,
    }
