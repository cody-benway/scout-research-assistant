from __future__ import annotations

import asyncio
import json
import logging
import os
from json import JSONDecodeError

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
    temperature=0.2,
)


def _extract_json_payload(raw: str) -> str:
    """Extract the most likely JSON object from model output."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def _invoke_report_json(prompt: str, timeout_s: int = 60) -> dict:
    async with asyncio.timeout(timeout_s):
        response = await _llm.ainvoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    payload = _extract_json_payload(content)
    return json.loads(payload)


async def synthesizer(state: ResearchState) -> dict:
    """Synthesize all search results into a structured research report."""
    writer = get_stream_writer()

    search_results = state.get("search_results", [])

    writer({
        "type": "step",
        "step": "synthesizing",
        "message": f"Synthesizing {len(search_results)} sources into a report...",
    })

    template = _jinja_env.get_template("synthesis.j2")
    prompt = template.render(
        query=state["query"],
        search_results=search_results,
    )

    synthesis_error: str | None = None
    try:
        report = await _invoke_report_json(prompt, timeout_s=60)
    except JSONDecodeError as exc:
        # Retry once with stronger output constraints before falling back.
        retry_prompt = (
            f"{prompt}\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "- Return ONLY a valid JSON object.\n"
            "- Do not include markdown fences.\n"
            "- Escape quotes/newlines correctly.\n"
            "- Ensure the final JSON parses with a strict parser."
        )
        try:
            report = await _invoke_report_json(retry_prompt, timeout_s=45)
            logger.warning("synthesizer: recovered from json parse failure on retry: %s", exc)
        except Exception as retry_exc:
            synthesis_error = f"Synthesis JSON parsing failed: {retry_exc}"
            logger.error("synthesizer: retry failed after parse error=%s", retry_exc)
            report = {
                "title": f"Research Report: {state['query']}",
                "summary": "An error occurred during synthesis. Partial results are shown below.",
                "key_findings": [],
                "sections": [
                    {
                        "heading": "Raw Findings",
                        "content": "\n\n".join(
                            f"**{r.get('title', 'Source')}**\n{r.get('content', '')[:300]}"
                            for r in search_results[:5]
                        ),
                    }
                ],
                "conclusion": "",
                "citations": [
                    {"index": i + 1, "title": r.get("title", ""), "url": r.get("url", "")}
                    for i, r in enumerate(search_results[:5])
                ],
            }
    except Exception as exc:
        synthesis_error = f"Synthesis failed: {exc}"
        logger.error("synthesizer: error=%s", exc)
        report = {
            "title": f"Research Report: {state['query']}",
            "summary": "An error occurred during synthesis. Partial results are shown below.",
            "key_findings": [],
            "sections": [
                {
                    "heading": "Raw Findings",
                    "content": "\n\n".join(
                        f"**{r.get('title', 'Source')}**\n{r.get('content', '')[:300]}"
                        for r in search_results[:5]
                    ),
                }
            ],
            "conclusion": "",
            "citations": [
                {"index": i + 1, "title": r.get("title", ""), "url": r.get("url", "")}
                for i, r in enumerate(search_results[:5])
            ],
        }

    citations = [c["url"] for c in report.get("citations", []) if c.get("url")]
    answer_draft = report.get("summary", "")

    writer({
        "type": "step",
        "step": "synthesizing",
        "message": "Report draft complete",
    })

    logger.info("synthesizer: sections=%d citations=%d", len(report.get("sections", [])), len(citations))

    return {
        "answer_draft": answer_draft,
        "citations": citations,
        "report": report,
        "synthesis_error": synthesis_error,
    }


async def reflector(state: ResearchState) -> dict:
    """Evaluate research completeness and decide whether to loop for more searches."""
    writer = get_stream_writer()

    writer({
        "type": "step",
        "step": "reflecting",
        "message": "Evaluating research completeness...",
    })

    template = _jinja_env.get_template("reflection.j2")
    prompt = template.render(
        query=state["query"],
        iteration=state.get("iteration", 1) - 1,
        max_iterations=state.get("max_iterations", 3),
        sub_queries=state.get("sub_queries", []),
        answer_draft=state.get("answer_draft", ""),
        num_docs=len(state.get("search_results", [])),
    )

    done = False
    try:
        async with asyncio.timeout(30):
            response = await _llm.ainvoke(prompt)
        content = response.content.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        should_continue = parsed.get("should_continue", False)

        iteration = state.get("iteration", 1)
        max_iterations = state.get("max_iterations", 3)

        if not should_continue or iteration >= max_iterations:
            done = True
            writer({
                "type": "step",
                "step": "reflecting",
                "message": "Research complete — moving to final synthesis.",
            })
        else:
            gaps = parsed.get("gaps", [])
            writer({
                "type": "step",
                "step": "reflecting",
                "message": f"Found {len(gaps)} gap(s) — running another search iteration.",
                "gaps": gaps,
            })
    except Exception as exc:
        logger.warning("reflector: error=%s — forcing done", exc)
        done = True

    return {"done": done}
