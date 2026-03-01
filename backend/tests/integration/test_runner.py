"""Integration tests for run_research_stream.

The LangGraph graph is replaced with a lightweight async generator so the
runner's event-routing, queue, and SSE-formatting logic can be tested end-to-end
without touching Gemini or Tavily.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FAKE_REPORT, make_state


# ---------------------------------------------------------------------------
# Fake graph helpers
# ---------------------------------------------------------------------------

def _make_fake_graph(stream_events: list[tuple[str, dict]]):
    """
    Return a mock graph whose astream() yields the given (mode, data) tuples.
    """
    async def _astream(initial_state, config, stream_mode):
        for event in stream_events:
            yield event

    mock_graph = MagicMock()
    mock_graph.astream = _astream
    return mock_graph


def _step_event(step: str, message: str) -> tuple[str, dict]:
    return ("custom", {"type": "step", "step": step, "message": message})


def _update_event(node: str, update: dict) -> tuple[str, dict]:
    return ("updates", {node: update})


# ---------------------------------------------------------------------------
# run_research_stream
# ---------------------------------------------------------------------------

class TestRunResearchStream:
    async def test_emits_complete_event_with_report(self):
        from app.agent.runner import run_research_stream

        stream_events = [
            _step_event("planning", "Planning..."),
            _step_event("searching", "Searching..."),
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        fake_graph = _make_fake_graph(stream_events)
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        complete = [e for e in events if e["type"] == "complete"]
        assert len(complete) == 1
        assert complete[0]["report"]["title"] == FAKE_REPORT["title"]

    async def test_step_events_forwarded_to_queue(self):
        from app.agent.runner import run_research_stream

        stream_events = [
            _step_event("planning", "Planning..."),
            _step_event("searching", "Searching..."),
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        fake_graph = _make_fake_graph(stream_events)
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        step_events = [e for e in events if e["type"] == "step"]
        assert len(step_events) == 2

    async def test_returns_final_report(self):
        from app.agent.runner import run_research_stream

        stream_events = [
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        fake_graph = _make_fake_graph(stream_events)

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            result = await run_research_stream("test query", max_iterations=1)

        assert result == FAKE_REPORT

    async def test_emits_error_when_no_report_produced(self):
        from app.agent.runner import run_research_stream

        # Graph completes but never sets report
        stream_events = [
            _step_event("planning", "Planning..."),
        ]
        fake_graph = _make_fake_graph(stream_events)
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "no report" in error_events[0]["message"].lower()

    async def test_emits_degraded_flag_when_synthesis_error_present(self):
        from app.agent.runner import run_research_stream

        stream_events = [
            _update_event("synthesizer", {
                "report": FAKE_REPORT,
                "synthesis_error": "Synthesis JSON parsing failed: ...",
            }),
        ]
        fake_graph = _make_fake_graph(stream_events)
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        complete = [e for e in events if e["type"] == "complete"]
        assert complete[0]["degraded"] is True
        assert complete[0]["warning"] is not None

    async def test_complete_not_degraded_when_no_synthesis_error(self):
        from app.agent.runner import run_research_stream

        stream_events = [
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        fake_graph = _make_fake_graph(stream_events)
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        complete = [e for e in events if e["type"] == "complete"]
        assert complete[0]["degraded"] is False

    async def test_emits_error_event_on_graph_exception(self):
        from app.agent.runner import run_research_stream

        async def _bad_astream(*args, **kwargs):
            raise RuntimeError("graph exploded")
            yield  # make it an async generator

        mock_graph = MagicMock()
        mock_graph.astream = _bad_astream
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=mock_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1

    async def test_emits_error_on_recursion_limit(self):
        from app.agent.runner import run_research_stream
        from langgraph.errors import GraphRecursionError

        async def _recursion_astream(*args, **kwargs):
            raise GraphRecursionError("too deep")
            yield

        mock_graph = MagicMock()
        mock_graph.astream = _recursion_astream
        queue: asyncio.Queue = asyncio.Queue()

        with patch("app.agent.runner.get_graph", return_value=mock_graph):
            await run_research_stream("test query", max_iterations=1, queue=queue)

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "recursion" in error_events[0]["message"].lower()

    async def test_works_without_queue(self):
        """run_research_stream should not crash when queue=None."""
        from app.agent.runner import run_research_stream

        stream_events = [
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        fake_graph = _make_fake_graph(stream_events)

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            result = await run_research_stream("test query", max_iterations=1, queue=None)

        assert result == FAKE_REPORT


# ---------------------------------------------------------------------------
# stream_to_sse (SSE formatting layer)
# ---------------------------------------------------------------------------

class TestStreamToSse:
    async def _collect_sse(self, stream_events: list[tuple[str, dict]]) -> list[str]:
        from app.agent.runner import stream_to_sse

        fake_graph = _make_fake_graph(stream_events)
        chunks = []

        with patch("app.agent.runner.get_graph", return_value=fake_graph):
            async for chunk in stream_to_sse("test query", max_iterations=1):
                chunks.append(chunk)

        return chunks

    async def test_each_event_prefixed_with_data(self):
        stream_events = [
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        chunks = await self._collect_sse(stream_events)
        data_chunks = [c for c in chunks if c.startswith("data:")]
        assert len(data_chunks) >= 1

    async def test_each_event_ends_with_double_newline(self):
        stream_events = [
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        chunks = await self._collect_sse(stream_events)
        data_chunks = [c for c in chunks if c.startswith("data:")]
        assert all(c.endswith("\n\n") for c in data_chunks)

    async def test_data_payload_is_valid_json(self):
        stream_events = [
            _step_event("planning", "Planning..."),
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
        ]
        chunks = await self._collect_sse(stream_events)
        for chunk in chunks:
            if chunk.startswith("data:"):
                payload = chunk[len("data:"):].strip()
                parsed = json.loads(payload)
                assert isinstance(parsed, dict)

    async def test_stops_after_complete_event(self):
        """Generator should terminate after emitting the complete event."""
        stream_events = [
            _step_event("planning", "Planning..."),
            _update_event("synthesizer", {"report": FAKE_REPORT, "synthesis_error": None}),
            # This step would appear after complete — should not be yielded
            _step_event("searching", "Should not appear"),
        ]
        chunks = await self._collect_sse(stream_events)
        # All chunks after complete should not exist
        complete_idx = next(
            (i for i, c in enumerate(chunks) if "complete" in c), None
        )
        assert complete_idx is not None
        assert len(chunks) == complete_idx + 1
