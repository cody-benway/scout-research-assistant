"""Integration tests for the FastAPI research endpoints.

The research agent (run_research_stream) is patched so no real LLM or
search calls are made.  httpx.AsyncClient drives the ASGI app directly.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import FAKE_REPORT


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from app.main import app as _app
    return _app


@pytest.fixture
def async_client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Helper: build a fake run_research_stream that pushes events to the queue
# ---------------------------------------------------------------------------

def _make_fake_runner(events: list[dict]):
    """
    Return an async function with the same signature as run_research_stream
    that pushes the given events into the queue and returns the report (if any).
    """
    async def _fake(query: str, max_iterations: int = 3, queue: asyncio.Queue | None = None):
        for event in events:
            if queue is not None:
                await queue.put(event)
        report = next((e.get("report") for e in events if e.get("type") == "complete"), None)
        return report

    return _fake


# ---------------------------------------------------------------------------
# Health check (sanity)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_ok(self, async_client):
        async with async_client as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /research — job creation
# ---------------------------------------------------------------------------

class TestStartResearch:
    async def test_returns_202_with_job_id(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        with patch("app.api.research.run_research_stream", fake_runner):
            async with async_client as client:
                resp = await client.post(
                    "/research",
                    json={"query": "How does photosynthesis work?"},
                )

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert len(body["job_id"]) > 0

    async def test_returns_pending_status(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        with patch("app.api.research.run_research_stream", fake_runner):
            async with async_client as client:
                resp = await client.post(
                    "/research",
                    json={"query": "How does photosynthesis work?"},
                )

        assert resp.json()["status"] == "pending"

    async def test_rejects_query_too_short(self, async_client):
        async with async_client as client:
            resp = await client.post("/research", json={"query": "ab"})
        assert resp.status_code == 422

    async def test_rejects_query_too_long(self, async_client):
        async with async_client as client:
            resp = await client.post("/research", json={"query": "x" * 501})
        assert resp.status_code == 422

    async def test_rejects_max_iterations_out_of_range(self, async_client):
        async with async_client as client:
            resp = await client.post(
                "/research",
                json={"query": "valid query here", "max_iterations": 10},
            )
        assert resp.status_code == 422

    async def test_accepts_custom_max_iterations(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        with patch("app.api.research.run_research_stream", fake_runner):
            async with async_client as client:
                resp = await client.post(
                    "/research",
                    json={"query": "valid query here", "max_iterations": 2},
                )

        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# GET /research/{job_id}/stream — SSE streaming
# ---------------------------------------------------------------------------

class TestStreamResearch:
    async def _start_job(self, client, fake_runner) -> str:
        with patch("app.api.research.run_research_stream", fake_runner):
            resp = await client.post(
                "/research",
                json={"query": "How does photosynthesis work?"},
            )
        return resp.json()["job_id"]

    async def _collect_sse(self, client, job_id: str, fake_runner) -> list[dict]:
        """Consume the SSE stream and return parsed event payloads."""
        events = []
        with patch("app.api.research.run_research_stream", fake_runner):
            async with client.stream("GET", f"/research/{job_id}/stream") as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        payload = line[len("data:"):].strip()
                        events.append(json.loads(payload))
        return events

    async def test_stream_returns_200(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "step", "step": "planning", "message": "Planning..."},
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        async with async_client as client:
            job_id = await self._start_job(client, fake_runner)
            # Allow background task to start
            await asyncio.sleep(0.05)
            async with client.stream("GET", f"/research/{job_id}/stream") as resp:
                assert resp.status_code == 200

    async def test_stream_returns_404_for_unknown_job(self, async_client):
        async with async_client as client:
            resp = await client.get("/research/nonexistent-job-id/stream")
        assert resp.status_code == 404

    async def test_stream_delivers_complete_event(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        async with async_client as client:
            job_id = await self._start_job(client, fake_runner)
            await asyncio.sleep(0.05)
            events = await self._collect_sse(client, job_id, fake_runner)

        complete = [e for e in events if e.get("type") == "complete"]
        assert len(complete) == 1
        assert complete[0]["report"]["title"] == FAKE_REPORT["title"]

    async def test_stream_delivers_step_events(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "step", "step": "planning", "message": "Planning..."},
            {"type": "step", "step": "searching", "message": "Searching..."},
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        async with async_client as client:
            job_id = await self._start_job(client, fake_runner)
            await asyncio.sleep(0.05)
            events = await self._collect_sse(client, job_id, fake_runner)

        step_events = [e for e in events if e.get("type") == "step"]
        assert len(step_events) >= 2

    async def test_stream_delivers_degraded_complete(self, async_client):
        fake_runner = _make_fake_runner([
            {
                "type": "complete",
                "report": FAKE_REPORT,
                "degraded": True,
                "warning": "Synthesis JSON parsing failed: ...",
            },
        ])

        async with async_client as client:
            job_id = await self._start_job(client, fake_runner)
            await asyncio.sleep(0.05)
            events = await self._collect_sse(client, job_id, fake_runner)

        complete = [e for e in events if e.get("type") == "complete"]
        assert complete[0]["degraded"] is True
        assert complete[0]["warning"] is not None

    async def test_stream_content_type_is_text_event_stream(self, async_client):
        fake_runner = _make_fake_runner([
            {"type": "complete", "report": FAKE_REPORT, "degraded": False, "warning": None},
        ])

        async with async_client as client:
            job_id = await self._start_job(client, fake_runner)
            await asyncio.sleep(0.05)
            async with client.stream("GET", f"/research/{job_id}/stream") as resp:
                assert "text/event-stream" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# GET /research/{job_id}/result — polling endpoint
# ---------------------------------------------------------------------------

class TestGetResult:
    async def test_returns_404_for_unknown_job(self, async_client):
        async with async_client as client:
            resp = await client.get("/research/unknown-id/result")
        assert resp.status_code == 404

    async def test_returns_202_while_job_running(self, async_client):
        """
        If the job is still in running state, /result should return 202.
        We set the job status to running directly in the in-memory store
        rather than relying on background-task timing.
        """
        import uuid
        from app.api.research import _job_results, _job_queues
        from app.models import JobStatus

        job_id = str(uuid.uuid4())
        _job_queues[job_id] = asyncio.Queue()
        _job_results[job_id] = {"status": JobStatus.running, "report": None, "error": None}

        async with async_client as client:
            result_resp = await client.get(f"/research/{job_id}/result")

        assert result_resp.status_code == 202

        # Cleanup
        _job_queues.pop(job_id, None)
        _job_results.pop(job_id, None)
