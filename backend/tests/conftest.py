"""Shared fixtures and helpers for all tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fake LLM response helpers
# ---------------------------------------------------------------------------

def make_llm_response(content: str) -> SimpleNamespace:
    """Return an object that looks like a LangChain AIMessage."""
    return SimpleNamespace(content=content)


def make_llm(content: str) -> AsyncMock:
    """Return an AsyncMock that mimics ChatGoogleGenerativeAI.ainvoke."""
    mock = AsyncMock(return_value=make_llm_response(content))
    return mock


# ---------------------------------------------------------------------------
# Fake stream writer
# ---------------------------------------------------------------------------

@pytest.fixture
def captured_events() -> list[dict]:
    return []


@pytest.fixture
def fake_writer(captured_events: list[dict]):
    """A callable that records every event written by a node."""
    def _writer(event: dict) -> None:
        captured_events.append(event)
    return _writer


# ---------------------------------------------------------------------------
# Minimal ResearchState factory
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    base: dict = {
        "query": "How does photosynthesis work?",
        "sub_queries": [],
        "search_results": [],
        "search_expected": 0,
        "search_completed": 0,
        "answer_draft": "",
        "citations": [],
        "report": None,
        "synthesis_error": None,
        "iteration": 0,
        "max_iterations": 3,
        "done": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Canonical fake report / reflection payloads
# ---------------------------------------------------------------------------

FAKE_REPORT = {
    "title": "Research Report: How does photosynthesis work?",
    "summary": "Photosynthesis converts light energy into chemical energy.",
    "key_findings": ["Plants use chlorophyll", "CO2 + H2O → glucose + O2"],
    "sections": [{"heading": "Overview", "content": "Photosynthesis is..."}],
    "conclusion": "A vital process.",
    "citations": [{"index": 1, "title": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Photosynthesis"}],
}

FAKE_REFLECTION_CONTINUE = {
    "gaps": ["Need more on light reactions"],
    "should_continue": True,
    "reasoning": "Missing detail on light-dependent reactions.",
    "confidence": "medium",
}

FAKE_REFLECTION_DONE = {
    "gaps": [],
    "should_continue": False,
    "reasoning": "Coverage is sufficient.",
    "confidence": "high",
}

FAKE_QUERIES = {
    "queries": [
        "What is photosynthesis?",
        "How does chlorophyll absorb light?",
        "What are the products of photosynthesis?",
        "Where does photosynthesis occur in the cell?",
    ]
}

FAKE_SEARCH_RESULTS = [
    {
        "title": "Photosynthesis - Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Photosynthesis",
        "content": "Photosynthesis is the process used by plants...",
        "raw_content": "Full article text...",
        "score": 0.95,
    }
]
