"""Claude integration — wording only.

Claude rewrites the inspector's notes into concise, professional report text.
It receives the results *and* the statuses already calculated by
calculation_service, and is instructed to report them as given. It never
decides PASS / FAIL and must not invent results, standards or criteria.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel, Field

from config import settings
from models.evaluation import EvaluationResult
from models.inspection import InspectionReport

SYSTEM_PROMPT = """\
You are a technical writer in a metals Quality Control laboratory. You turn an \
inspector's rough notes into concise, professional wording for a one-page \
inspection report.

Strict rules:
- Use only the facts in the data provided. Never invent test results, values, \
units, standards, specifications, acceptance criteria, specimen details or \
observations.
- Do not perform or re-check any calculation or comparison. The status of each \
test and the overall result were determined by the laboratory software; state \
them exactly as given and never contradict them.
- Where a criterion is "Acceptance criterion not specified", say so plainly; \
do not suggest a limit.
- Keep the inspector's meaning. If a note is vague, make it professional without \
adding technical detail that is not there.
- Plain text only: no markdown, bullet points or headings.
- Be brief; the report must fit on one A4 page.

Fields to produce:
- summary: 2-4 sentences, at most 70 words, summarising the inspection findings \
and the overall result.
- microstructure: at most 40 words, a professional restatement of the \
microstructure observation. Empty string if no observation was given.
- remarks: at most 40 words, a professional restatement of the inspector's \
remarks. Empty string if no remarks were given.
"""


class ClaudeServiceError(Exception):
    """A user-presentable error from the AI wording service."""


class _WordingOutput(BaseModel):
    summary: str = Field(description="Concise inspection summary, at most 70 words.")
    microstructure: str = Field(description="Professional microstructure wording, at most 40 words.")
    remarks: str = Field(description="Professional remarks, at most 40 words.")


@dataclass
class AIWording:
    summary: str
    microstructure: str
    remarks: str


def is_configured() -> bool:
    return bool(os.getenv(settings.ANTHROPIC_API_KEY_ENV, "").strip())


def _clip(text: str, limit: int) -> str:
    """Keep AI text within the report's space budget (cut at a word boundary)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def build_prompt_payload(report: InspectionReport, evaluation: EvaluationResult) -> dict:
    """The facts sent to Claude. Kept explicit so it is easy to audit."""
    info, m = report.info, report.metallography
    return {
        "inspection": {
            "material": info.material,
            "grade": info.grade,
            "heat_batch": info.heat_batch,
            "specification": info.specification,
        },
        "test_results": [
            {
                "test": i.name,
                "result": i.result_text,
                "requirement": i.requirement_text,
                "status": i.status.value,
                "mandatory": i.mandatory,
                "note": i.note,
            }
            for i in evaluation.items
        ],
        "overall_result": evaluation.overall.value,
        "overall_result_reasons": evaluation.reasons,
        "metallography": {
            "etchant": m.etchant,
            "magnification": m.magnification,
            "microstructure_observation_raw": m.microstructure,
        },
        "inspector_remarks_raw": info.remarks,
    }


def generate_wording(report: InspectionReport, evaluation: EvaluationResult) -> AIWording:
    """Ask Claude for professional wording. Raises ClaudeServiceError on any failure."""
    if not is_configured():
        raise ClaudeServiceError(
            f"{settings.ANTHROPIC_API_KEY_ENV} is not set. Add it to your environment or "
            "to a .env file (see .env.example) to use AI wording. Evaluation and report "
            "generation work without it."
        )

    client = anthropic.Anthropic(
        api_key=os.environ[settings.ANTHROPIC_API_KEY_ENV].strip(),
        timeout=settings.CLAUDE_TIMEOUT_SECONDS,
    )
    payload = json.dumps(build_prompt_payload(report, evaluation), indent=2, ensure_ascii=False)

    try:
        response = client.beta.messages.parse(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Inspection data (JSON):\n{payload}\n\nWrite the report wording.",
            }],
            output_format=_WordingOutput,
            output_config={"effort": settings.CLAUDE_EFFORT},
            # If a safety classifier declines, retry server-side on the
            # recommended fallback model instead of failing.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise ClaudeServiceError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError:
        raise ClaudeServiceError("The Anthropic API key does not have permission for this model.")
    except anthropic.RateLimitError:
        raise ClaudeServiceError("Anthropic API rate limit reached. Please wait and try again.")
    except anthropic.APIStatusError as e:
        raise ClaudeServiceError(f"Anthropic API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        raise ClaudeServiceError("Could not reach the Anthropic API. Check your internet connection.")

    if response.stop_reason == "refusal":
        raise ClaudeServiceError("Claude declined to produce wording for this request.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ClaudeServiceError("Claude returned an incomplete response. Please try again.")

    out = response.parsed_output
    return AIWording(
        summary=_clip(out.summary, settings.MAX_CHARS_SUMMARY),
        microstructure=_clip(out.microstructure, settings.MAX_CHARS_OBSERVATION),
        remarks=_clip(out.remarks, settings.MAX_CHARS_REMARKS),
    )
