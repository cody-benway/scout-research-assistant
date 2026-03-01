"""Unit tests for the synthesizer and reflector nodes.

All LLM calls and LangGraph stream-writer calls are patched so no real
Gemini API tokens are consumed.
"""
from __future__ import annotations

import json
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    FAKE_REFLECTION_CONTINUE,
    FAKE_REFLECTION_DONE,
    FAKE_REPORT,
    FAKE_SEARCH_RESULTS,
    make_llm_response,
    make_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_writer():
    """Context manager: replace get_stream_writer with a no-op writer."""
    return patch(
        "app.agent.nodes.synthesizer.get_stream_writer",
        return_value=lambda _event: None,
    )


def _patch_llm(side_effect=None, return_value=None):
    """Patch the module-level _llm used by synthesizer / reflector."""
    if side_effect is not None:
        mock = AsyncMock(side_effect=side_effect)
    else:
        mock = AsyncMock(return_value=make_llm_response(json.dumps(return_value)))
    return patch("app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock))


# ---------------------------------------------------------------------------
# _extract_json_payload
# ---------------------------------------------------------------------------

class TestExtractJsonPayload:
    def test_plain_json(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        raw = '{"key": "value"}'
        assert _extract_json_payload(raw) == '{"key": "value"}'

    def test_strips_markdown_json_fence(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        raw = '```json\n{"key": "value"}\n```'
        result = _extract_json_payload(raw)
        assert json.loads(result) == {"key": "value"}

    def test_strips_plain_markdown_fence(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        raw = '```\n{"key": "value"}\n```'
        result = _extract_json_payload(raw)
        assert json.loads(result) == {"key": "value"}

    def test_extracts_json_from_prose_prefix(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        raw = 'Here is the result:\n{"key": "value"}\nThat is all.'
        result = _extract_json_payload(raw)
        assert json.loads(result) == {"key": "value"}

    def test_returns_text_unchanged_when_no_braces(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        raw = "no json here"
        assert _extract_json_payload(raw) == "no json here"

    def test_handles_nested_objects(self):
        from app.agent.nodes.synthesizer import _extract_json_payload
        payload = {"outer": {"inner": [1, 2, 3]}}
        raw = json.dumps(payload)
        result = _extract_json_payload(raw)
        assert json.loads(result) == payload


# ---------------------------------------------------------------------------
# synthesizer — happy path
# ---------------------------------------------------------------------------

class TestSynthesizerHappyPath:
    async def test_returns_report_on_valid_llm_response(self):
        from app.agent.nodes.synthesizer import synthesizer

        state = make_state(
            search_results=FAKE_SEARCH_RESULTS,
            query="How does photosynthesis work?",
        )

        with _patch_writer(), _patch_llm(return_value=FAKE_REPORT):
            result = await synthesizer(state)

        assert result["report"]["title"] == FAKE_REPORT["title"]
        assert result["synthesis_error"] is None

    async def test_extracts_citations_from_report(self):
        from app.agent.nodes.synthesizer import synthesizer

        state = make_state(search_results=FAKE_SEARCH_RESULTS)

        with _patch_writer(), _patch_llm(return_value=FAKE_REPORT):
            result = await synthesizer(state)

        assert "https://en.wikipedia.org/wiki/Photosynthesis" in result["citations"]

    async def test_sets_answer_draft_from_summary(self):
        from app.agent.nodes.synthesizer import synthesizer

        state = make_state(search_results=FAKE_SEARCH_RESULTS)

        with _patch_writer(), _patch_llm(return_value=FAKE_REPORT):
            result = await synthesizer(state)

        assert result["answer_draft"] == FAKE_REPORT["summary"]

    async def test_emits_two_step_events(self):
        from app.agent.nodes.synthesizer import synthesizer

        events: list[dict] = []

        with (
            patch(
                "app.agent.nodes.synthesizer.get_stream_writer",
                return_value=lambda e: events.append(e),
            ),
            _patch_llm(return_value=FAKE_REPORT),
        ):
            await synthesizer(make_state(search_results=FAKE_SEARCH_RESULTS))

        step_types = [e.get("step") for e in events if e.get("type") == "step"]
        assert step_types.count("synthesizing") == 2

    async def test_handles_fenced_json_from_llm(self):
        from app.agent.nodes.synthesizer import synthesizer

        fenced = f"```json\n{json.dumps(FAKE_REPORT)}\n```"
        mock_llm = AsyncMock(return_value=make_llm_response(fenced))

        with _patch_writer(), patch("app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)):
            result = await synthesizer(make_state(search_results=FAKE_SEARCH_RESULTS))

        assert result["synthesis_error"] is None
        assert result["report"]["title"] == FAKE_REPORT["title"]


# ---------------------------------------------------------------------------
# synthesizer — JSON parse failure → retry → success
# ---------------------------------------------------------------------------

class TestSynthesizerRetry:
    async def test_retries_on_json_decode_error_and_succeeds(self):
        from app.agent.nodes.synthesizer import synthesizer

        call_count = 0

        async def _llm_side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return make_llm_response("not valid json {{{{")
            return make_llm_response(json.dumps(FAKE_REPORT))

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_llm_side_effect)
        ):
            result = await synthesizer(make_state(search_results=FAKE_SEARCH_RESULTS))

        assert call_count == 2
        assert result["synthesis_error"] is None
        assert result["report"]["title"] == FAKE_REPORT["title"]

    async def test_falls_back_when_retry_also_fails(self):
        from app.agent.nodes.synthesizer import synthesizer

        async def _always_bad(prompt):
            return make_llm_response("not valid json {{{{")

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_always_bad)
        ):
            result = await synthesizer(make_state(search_results=FAKE_SEARCH_RESULTS))

        assert result["synthesis_error"] is not None
        assert "Synthesis JSON parsing failed" in result["synthesis_error"]
        assert result["report"]["summary"].startswith("An error occurred")

    async def test_fallback_report_includes_raw_findings_section(self):
        from app.agent.nodes.synthesizer import synthesizer

        async def _always_bad(prompt):
            return make_llm_response("{{bad")

        state = make_state(search_results=FAKE_SEARCH_RESULTS)

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_always_bad)
        ):
            result = await synthesizer(state)

        headings = [s["heading"] for s in result["report"]["sections"]]
        assert "Raw Findings" in headings

    async def test_fallback_report_includes_up_to_5_citations(self):
        from app.agent.nodes.synthesizer import synthesizer

        many_results = [
            {"title": f"Source {i}", "url": f"https://example.com/{i}", "content": "x"}
            for i in range(8)
        ]

        async def _always_bad(prompt):
            return make_llm_response("{{bad")

        state = make_state(search_results=many_results)

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_always_bad)
        ):
            result = await synthesizer(state)

        assert len(result["report"]["citations"]) == 5


# ---------------------------------------------------------------------------
# synthesizer — non-JSON exception (e.g. timeout)
# ---------------------------------------------------------------------------

class TestSynthesizerNonJsonError:
    async def test_sets_synthesis_error_on_unexpected_exception(self):
        from app.agent.nodes.synthesizer import synthesizer

        async def _raise(prompt):
            raise RuntimeError("network timeout")

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_raise)
        ):
            result = await synthesizer(make_state())

        assert result["synthesis_error"] is not None
        assert "Synthesis failed" in result["synthesis_error"]

    async def test_still_returns_fallback_report_on_exception(self):
        from app.agent.nodes.synthesizer import synthesizer

        async def _raise(prompt):
            raise RuntimeError("network timeout")

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_raise)
        ):
            result = await synthesizer(make_state())

        assert result["report"] is not None
        assert result["report"]["title"].startswith("Research Report:")


# ---------------------------------------------------------------------------
# reflector
# ---------------------------------------------------------------------------

class TestReflector:
    async def test_returns_done_false_when_should_continue(self):
        from app.agent.nodes.synthesizer import reflector

        state = make_state(iteration=1, max_iterations=3)
        mock_llm = AsyncMock(
            return_value=make_llm_response(json.dumps(FAKE_REFLECTION_CONTINUE))
        )

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)
        ):
            result = await reflector(state)

        assert result["done"] is False

    async def test_returns_done_true_when_should_not_continue(self):
        from app.agent.nodes.synthesizer import reflector

        state = make_state(iteration=1, max_iterations=3)
        mock_llm = AsyncMock(
            return_value=make_llm_response(json.dumps(FAKE_REFLECTION_DONE))
        )

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)
        ):
            result = await reflector(state)

        assert result["done"] is True

    async def test_forces_done_at_max_iterations(self):
        from app.agent.nodes.synthesizer import reflector

        # iteration == max_iterations means we've exhausted the budget
        state = make_state(iteration=3, max_iterations=3)
        mock_llm = AsyncMock(
            return_value=make_llm_response(json.dumps(FAKE_REFLECTION_CONTINUE))
        )

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)
        ):
            result = await reflector(state)

        assert result["done"] is True

    async def test_forces_done_on_llm_error(self):
        from app.agent.nodes.synthesizer import reflector

        async def _raise(prompt):
            raise RuntimeError("timeout")

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=_raise)
        ):
            result = await reflector(make_state())

        assert result["done"] is True

    async def test_forces_done_on_bad_json(self):
        from app.agent.nodes.synthesizer import reflector

        mock_llm = AsyncMock(return_value=make_llm_response("not json"))

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)
        ):
            result = await reflector(make_state())

        assert result["done"] is True

    async def test_emits_gaps_step_when_continuing(self):
        from app.agent.nodes.synthesizer import reflector

        events: list[dict] = []
        state = make_state(iteration=1, max_iterations=3)
        mock_llm = AsyncMock(
            return_value=make_llm_response(json.dumps(FAKE_REFLECTION_CONTINUE))
        )

        with (
            patch(
                "app.agent.nodes.synthesizer.get_stream_writer",
                return_value=lambda e: events.append(e),
            ),
            patch("app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)),
        ):
            await reflector(state)

        gap_events = [e for e in events if e.get("step") == "reflecting" and "gap" in e.get("message", "")]
        assert len(gap_events) == 1
        assert gap_events[0].get("gaps") == FAKE_REFLECTION_CONTINUE["gaps"]

    async def test_handles_fenced_json_reflection(self):
        from app.agent.nodes.synthesizer import reflector

        fenced = f"```json\n{json.dumps(FAKE_REFLECTION_DONE)}\n```"
        mock_llm = AsyncMock(return_value=make_llm_response(fenced))

        with _patch_writer(), patch(
            "app.agent.nodes.synthesizer._llm", new=MagicMock(ainvoke=mock_llm)
        ):
            result = await reflector(make_state())

        assert result["done"] is True
