"""Unit tests for the query_planner node.

No real LLM or LangGraph infrastructure is used.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FAKE_QUERIES, make_llm_response, make_state


def _patch_writer(events: list[dict] | None = None):
    writer = (lambda e: events.append(e)) if events is not None else (lambda _: None)
    return patch(
        "app.agent.nodes.query_planner.get_stream_writer",
        return_value=writer,
    )


def _patch_llm(return_value: dict):
    mock = AsyncMock(return_value=make_llm_response(json.dumps(return_value)))
    return patch("app.agent.nodes.query_planner._llm", new=MagicMock(ainvoke=mock))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestQueryPlannerHappyPath:
    async def test_returns_sub_queries_list(self):
        from app.agent.nodes.query_planner import query_planner

        with _patch_writer(), _patch_llm(FAKE_QUERIES):
            result = await query_planner(make_state())

        assert result["sub_queries"] == FAKE_QUERIES["queries"]

    async def test_increments_iteration(self):
        from app.agent.nodes.query_planner import query_planner

        state = make_state(iteration=1)

        with _patch_writer(), _patch_llm(FAKE_QUERIES):
            result = await query_planner(state)

        assert result["iteration"] == 2

    async def test_sets_search_expected_to_query_count(self):
        from app.agent.nodes.query_planner import query_planner

        with _patch_writer(), _patch_llm(FAKE_QUERIES):
            result = await query_planner(make_state())

        assert result["search_expected"] == len(FAKE_QUERIES["queries"])

    async def test_resets_search_completed_to_zero(self):
        from app.agent.nodes.query_planner import query_planner

        state = make_state(search_completed=5)

        with _patch_writer(), _patch_llm(FAKE_QUERIES):
            result = await query_planner(state)

        assert result["search_completed"] == 0

    async def test_resets_search_results_to_empty_list(self):
        from app.agent.nodes.query_planner import query_planner

        state = make_state(search_results=[{"title": "old"}])

        with _patch_writer(), _patch_llm(FAKE_QUERIES):
            result = await query_planner(state)

        assert result["search_results"] == []

    async def test_emits_two_planning_step_events(self):
        from app.agent.nodes.query_planner import query_planner

        events: list[dict] = []

        with _patch_writer(events), _patch_llm(FAKE_QUERIES):
            await query_planner(make_state())

        planning_events = [e for e in events if e.get("step") == "planning"]
        assert len(planning_events) == 2

    async def test_second_event_includes_queries(self):
        from app.agent.nodes.query_planner import query_planner

        events: list[dict] = []

        with _patch_writer(events), _patch_llm(FAKE_QUERIES):
            await query_planner(make_state())

        second = [e for e in events if e.get("queries")]
        assert len(second) == 1
        assert second[0]["queries"] == FAKE_QUERIES["queries"]

    async def test_iteration_in_step_event_is_one_based(self):
        from app.agent.nodes.query_planner import query_planner

        events: list[dict] = []
        state = make_state(iteration=0)

        with _patch_writer(events), _patch_llm(FAKE_QUERIES):
            await query_planner(state)

        first_event = events[0]
        assert first_event["iteration"] == 1


# ---------------------------------------------------------------------------
# Fenced JSON from LLM
# ---------------------------------------------------------------------------

class TestQueryPlannerFencedJson:
    async def test_strips_json_fence(self):
        from app.agent.nodes.query_planner import query_planner

        fenced = f"```json\n{json.dumps(FAKE_QUERIES)}\n```"
        mock = AsyncMock(return_value=make_llm_response(fenced))

        with _patch_writer(), patch(
            "app.agent.nodes.query_planner._llm", new=MagicMock(ainvoke=mock)
        ):
            result = await query_planner(make_state())

        assert result["sub_queries"] == FAKE_QUERIES["queries"]

    async def test_strips_plain_fence(self):
        from app.agent.nodes.query_planner import query_planner

        fenced = f"```\n{json.dumps(FAKE_QUERIES)}\n```"
        mock = AsyncMock(return_value=make_llm_response(fenced))

        with _patch_writer(), patch(
            "app.agent.nodes.query_planner._llm", new=MagicMock(ainvoke=mock)
        ):
            result = await query_planner(make_state())

        assert result["sub_queries"] == FAKE_QUERIES["queries"]


# ---------------------------------------------------------------------------
# LLM error propagation (query_planner does not catch — it should bubble up)
# ---------------------------------------------------------------------------

class TestQueryPlannerErrorPropagation:
    async def test_raises_on_invalid_json(self):
        from app.agent.nodes.query_planner import query_planner

        mock = AsyncMock(return_value=make_llm_response("not json"))

        with _patch_writer(), patch(
            "app.agent.nodes.query_planner._llm", new=MagicMock(ainvoke=mock)
        ):
            with pytest.raises(Exception):
                await query_planner(make_state())

    async def test_raises_on_llm_exception(self):
        from app.agent.nodes.query_planner import query_planner

        async def _raise(prompt):
            raise RuntimeError("API error")

        with _patch_writer(), patch(
            "app.agent.nodes.query_planner._llm", new=MagicMock(ainvoke=_raise)
        ):
            with pytest.raises(RuntimeError, match="API error"):
                await query_planner(make_state())
