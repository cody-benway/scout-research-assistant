from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from langgraph.managed import RemainingSteps


class ResearchState(TypedDict):
    query: str
    sub_queries: list[str]
    # Parallel reducer — multiple workers append without clobbering
    search_results: Annotated[list[dict], add]
    # Barrier counters for fan-in
    search_expected: int
    search_completed: Annotated[int, add]
    # Output
    answer_draft: str
    citations: list[str]
    report: dict | None
    synthesis_error: str | None
    # Loop control
    iteration: int
    max_iterations: int
    done: bool
    remaining_steps: RemainingSteps
