from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.models import (
    JobCreatedResponse,
    JobResultResponse,
    JobStatus,
    ResearchRequest,
)
from app.agent.runner import run_research_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])

# In-memory job store — sufficient for single-process deployment
_job_queues: dict[str, asyncio.Queue] = {}
_job_results: dict[str, dict] = {}


async def _run_job(job_id: str, query: str, max_iterations: int) -> None:
    """Background task: run the research agent and store the result."""
    queue = _job_queues[job_id]
    _job_results[job_id]["status"] = JobStatus.running

    report = await run_research_stream(query, max_iterations=max_iterations, queue=queue)

    if report:
        _job_results[job_id]["status"] = JobStatus.complete
        _job_results[job_id]["report"] = report
    else:
        _job_results[job_id]["status"] = JobStatus.error
        _job_results[job_id]["error"] = "Agent completed without producing a report."


@router.post("", status_code=202, response_model=JobCreatedResponse)
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start a new research job. Returns a job_id immediately (HTTP 202)."""
    job_id = str(uuid.uuid4())
    _job_queues[job_id] = asyncio.Queue()
    _job_results[job_id] = {
        "status": JobStatus.pending,
        "report": None,
        "error": None,
    }

    background_tasks.add_task(_run_job, job_id, request.query, request.max_iterations)
    logger.info("start_research: job_id=%s query=%r", job_id, request.query)

    return JobCreatedResponse(job_id=job_id)


@router.get("/{job_id}/stream")
async def stream_research(job_id: str):
    """
    SSE endpoint — streams agent progress events until complete or error.
    Each event: data: {...}\\n\\n
    """
    if job_id not in _job_queues:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        queue = _job_queues[job_id]
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"

                if event.get("type") in ("complete", "error"):
                    _job_queues.pop(job_id, None)
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_result(job_id: str):
    """Return the final research report. Returns 202 if the job is still running."""
    if job_id not in _job_results:
        raise HTTPException(status_code=404, detail="Job not found")

    state = _job_results[job_id]
    status = state["status"]

    if status in (JobStatus.pending, JobStatus.running):
        raise HTTPException(status_code=202, detail="Job is still running")

    return JobResultResponse(
        job_id=job_id,
        status=status,
        report=state.get("report"),
        error=state.get("error"),
    )
