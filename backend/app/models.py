from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    error = "error"


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="The research topic or question")
    max_iterations: int = Field(default=3, ge=1, le=5, description="Max research loop iterations (1-5)")


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.pending


class ReportSection(BaseModel):
    heading: str
    content: str


class ReportCitation(BaseModel):
    index: int
    title: str
    url: str


class ResearchReport(BaseModel):
    title: str
    summary: str
    key_findings: list[str]
    sections: list[ReportSection]
    conclusion: str
    citations: list[ReportCitation]


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    report: ResearchReport | None = None
    error: str | None = None
