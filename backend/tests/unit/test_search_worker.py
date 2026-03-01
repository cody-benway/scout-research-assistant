"""Unit tests for the search_worker node.

The Tavily client is patched so no real HTTP requests are made.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import FAKE_SEARCH_RESULTS, make_state


RAW_TAVILY_RESULTS = [
    {
        "title": "Photosynthesis - Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Photosynthesis",
        "content": "Photosynthesis is the process used by plants...",
        "raw_content": "Full article text...",
        "score": 0.95,
    },
    {
        "title": "Chlorophyll explained",
        "url": "https://example.com/chlorophyll",
        "content": "Chlorophyll absorbs light...",
        "raw_content": "More detail...",
        "score": 0.88,
    },
]


def _patch_writer(events: list[dict] | None = None):
    writer = (lambda e: events.append(e)) if events is not None else (lambda _: None)
    return patch(
        "app.agent.nodes.search_worker.get_stream_writer",
        return_value=writer,
    )


_UNSET = object()


def _patch_search(return_value=_UNSET, side_effect=None):
    if side_effect is not None:
        mock = AsyncMock(side_effect=side_effect)
    else:
        mock = AsyncMock(return_value=RAW_TAVILY_RESULTS if return_value is _UNSET else return_value)
    return patch("app.agent.nodes.search_worker._search", mock)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestSearchWorkerHappyPath:
    async def test_returns_mapped_results(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "What is photosynthesis?", "query": "photosynthesis"}

        with _patch_writer(), _patch_search():
            result = await search_worker(state)

        assert len(result["search_results"]) == len(RAW_TAVILY_RESULTS)

    async def test_result_contains_expected_fields(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "What is photosynthesis?", "query": "photosynthesis"}

        with _patch_writer(), _patch_search():
            result = await search_worker(state)

        first = result["search_results"][0]
        assert first["title"] == RAW_TAVILY_RESULTS[0]["title"]
        assert first["url"] == RAW_TAVILY_RESULTS[0]["url"]
        assert first["content"] == RAW_TAVILY_RESULTS[0]["content"]
        assert first["score"] == RAW_TAVILY_RESULTS[0]["score"]

    async def test_result_includes_sub_query_field(self):
        from app.agent.nodes.search_worker import search_worker

        sub_query = "What is photosynthesis?"
        state = {"sub_query": sub_query, "query": "photosynthesis"}

        with _patch_writer(), _patch_search():
            result = await search_worker(state)

        assert all(r["sub_query"] == sub_query for r in result["search_results"])

    async def test_increments_search_completed_by_one(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "test query", "query": "test"}

        with _patch_writer(), _patch_search():
            result = await search_worker(state)

        assert result["search_completed"] == 1

    async def test_emits_searching_step_events(self):
        from app.agent.nodes.search_worker import search_worker

        events: list[dict] = []
        state = {"sub_query": "What is photosynthesis?", "query": "photosynthesis"}

        with _patch_writer(events), _patch_search():
            await search_worker(state)

        step_events = [e for e in events if e.get("step") == "searching"]
        assert len(step_events) == 2

    async def test_second_event_reports_result_count(self):
        from app.agent.nodes.search_worker import search_worker

        events: list[dict] = []
        state = {"sub_query": "What is photosynthesis?", "query": "photosynthesis"}

        with _patch_writer(events), _patch_search():
            await search_worker(state)

        second = [e for e in events if "Found" in e.get("message", "")]
        assert len(second) == 1
        assert str(len(RAW_TAVILY_RESULTS)) in second[0]["message"]

    async def test_handles_empty_results(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "obscure query", "query": "obscure"}

        with _patch_writer(), _patch_search(return_value=[]):
            result = await search_worker(state)

        assert result["search_results"] == []
        assert result["search_completed"] == 1


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestSearchWorkerFailure:
    async def test_returns_empty_results_on_exception(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "test", "query": "test"}

        with _patch_writer(), _patch_search(side_effect=RuntimeError("Tavily down")):
            result = await search_worker(state)

        assert result["search_results"] == []

    async def test_still_increments_search_completed_on_failure(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "test", "query": "test"}

        with _patch_writer(), _patch_search(side_effect=RuntimeError("Tavily down")):
            result = await search_worker(state)

        assert result["search_completed"] == 1

    async def test_emits_warning_event_on_failure(self):
        from app.agent.nodes.search_worker import search_worker

        events: list[dict] = []
        state = {"sub_query": "test", "query": "test"}

        with _patch_writer(events), _patch_search(side_effect=RuntimeError("Tavily down")):
            await search_worker(state)

        warning_events = [e for e in events if e.get("type") == "warning"]
        assert len(warning_events) == 1
        assert "test" in warning_events[0]["message"]

    async def test_does_not_raise_on_search_failure(self):
        from app.agent.nodes.search_worker import search_worker

        state = {"sub_query": "test", "query": "test"}

        with _patch_writer(), _patch_search(side_effect=Exception("any error")):
            result = await search_worker(state)

        assert isinstance(result, dict)

    async def test_missing_fields_in_raw_result_default_to_empty(self):
        from app.agent.nodes.search_worker import search_worker

        sparse_raw = [{"url": "https://example.com"}]
        state = {"sub_query": "test", "query": "test"}

        with _patch_writer(), _patch_search(return_value=sparse_raw):
            result = await search_worker(state)

        first = result["search_results"][0]
        assert first["title"] == ""
        assert first["content"] == ""
        assert first["score"] == 0.0
