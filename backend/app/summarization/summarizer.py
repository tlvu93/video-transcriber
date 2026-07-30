from __future__ import annotations

import logging
import os
import traceback
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from backend.app.summarization.config import (
    LLM_HOST,
    LLM_MODEL,
    SUMMARIZATION_CONTENT_PROFILE,
    SUMMARY_MAX_TOKENS,
)
from backend.app.summarization.ollama_client import get_ollama_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("summarizer")
SEGMENT_PROMPT_MAX_CHARS = 12000

PROFILE_INSTRUCTIONS = {
    "meeting": """Focus on decisions, action items, blockers, open questions, owners, and next steps.""",
    "podcast": """Focus on themes, guest insights, notable stories, memorable claims, and practical takeaways.""",
    "lecture": """Focus on key concepts, definitions, examples, learning objectives, and unresolved questions.""",
    "interview": """Focus on the interviewee's background, strongest answers, notable claims, and recurring themes.""",
    "generic": """Focus on the central topics, strongest insights, and the most important factual details.""",
}


class SummaryChapter(BaseModel):
    title: str
    start_time: float | None = None
    end_time: float | None = None
    summary: str


class SummaryHighlight(BaseModel):
    title: str
    detail: str
    timestamp_seconds: float | None = None


class SummaryActionItem(BaseModel):
    task: str
    owner: str | None = None
    due_hint: str | None = None


class SummaryEntity(BaseModel):
    name: str
    entity_type: str
    description: str | None = None


class StructuredSummaryBundle(BaseModel):
    content_profile: str = "generic"
    headline: str
    overview: str
    key_points: list[str] = Field(default_factory=list)
    chapters: list[SummaryChapter] = Field(default_factory=list)
    highlights: list[SummaryHighlight] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    action_items: list[SummaryActionItem] = Field(default_factory=list)
    entities: list[SummaryEntity] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def normalize_content_profile(content_profile: str | None) -> str:
    candidate = (content_profile or SUMMARIZATION_CONTENT_PROFILE or "generic").strip().lower()
    if candidate == "auto":
        return "generic"
    return candidate if candidate in PROFILE_INSTRUCTIONS else "generic"


def _format_timestamp_for_prompt(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"

    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _build_segment_cues(transcript_segments: Sequence[dict[str, Any]] | None) -> str:
    if not transcript_segments:
        return "No segment timeline cues were available."

    lines: list[str] = []
    total_chars = 0
    for segment in transcript_segments:
        text = " ".join(str(segment.get("text", "")).split())
        if not text:
            continue

        line = (
            f"{_format_timestamp_for_prompt(segment.get('start_time'))}"
            f" -> {_format_timestamp_for_prompt(segment.get('end_time'))}"
            f" | {segment.get('speaker') or 'Unknown speaker'}"
            f" | {text[:240]}"
        )
        if total_chars + len(line) > SEGMENT_PROMPT_MAX_CHARS:
            break
        lines.append(line)
        total_chars += len(line) + 1

    return "\n".join(lines) if lines else "No segment timeline cues were available."


def build_structured_summary_prompt(
    transcript_text: str,
    *,
    title_hint: str,
    content_profile: str,
    transcript_segments: Sequence[dict[str, Any]] | None = None,
) -> str:
    profile = normalize_content_profile(content_profile)
    profile_instructions = PROFILE_INSTRUCTIONS[profile]
    segment_cues = _build_segment_cues(transcript_segments)

    return f"""You are an expert editorial assistant summarizing spoken audio transcripts.

Asset title: {title_hint}
Content profile: {profile}

PRIMARY GOAL
Create a highly useful structured review package for a human editor reviewing this media.

PROFILE GUIDANCE
{profile_instructions}

OUTPUT RULES
- Return valid JSON only.
- Keep all fields grounded in the transcript.
- If a fact is ambiguous, reflect that uncertainty in the text.
- Use null for timestamps that cannot be inferred.
- Keep arrays concise and high-signal.
- Prefer 3 to 6 items for key_points, highlights, keywords, and entities when the transcript supports it.

Return a JSON object with exactly these keys:
- content_profile: string
- headline: string
- overview: string
- key_points: string[]
- chapters: object[] with title, start_time, end_time, summary
- highlights: object[] with title, detail, timestamp_seconds
- keywords: string[]
- action_items: object[] with task, owner, due_hint
- entities: object[] with name, entity_type, description
- open_questions: string[]
- risks: string[]

SEGMENT CUES
{segment_cues}

TRANSCRIPT
{transcript_text}
"""


def _clean_string_list(values: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            cleaned.append(normalized)
    return cleaned


def normalize_summary_bundle(bundle: StructuredSummaryBundle) -> StructuredSummaryBundle:
    content_profile = normalize_content_profile(bundle.content_profile)
    return StructuredSummaryBundle(
        content_profile=content_profile,
        headline=str(bundle.headline or "Summary").strip() or "Summary",
        overview=str(bundle.overview or "").strip()
        or "No overview was generated.",
        key_points=_clean_string_list(bundle.key_points),
        chapters=[
            SummaryChapter(
                title=str(chapter.title or "").strip() or "Untitled chapter",
                start_time=chapter.start_time,
                end_time=chapter.end_time,
                summary=str(chapter.summary or "").strip() or "No chapter summary available.",
            )
            for chapter in bundle.chapters
            if str(chapter.title or "").strip() or str(chapter.summary or "").strip()
        ],
        highlights=[
            SummaryHighlight(
                title=str(highlight.title or "").strip() or "Untitled highlight",
                detail=str(highlight.detail or "").strip() or "No highlight detail available.",
                timestamp_seconds=highlight.timestamp_seconds,
            )
            for highlight in bundle.highlights
            if str(highlight.title or "").strip() or str(highlight.detail or "").strip()
        ],
        keywords=_clean_string_list(bundle.keywords),
        action_items=[
            SummaryActionItem(
                task=str(item.task or "").strip() or "Follow up",
                owner=str(item.owner or "").strip() or None,
                due_hint=str(item.due_hint or "").strip() or None,
            )
            for item in bundle.action_items
            if str(item.task or "").strip()
        ],
        entities=[
            SummaryEntity(
                name=str(entity.name or "").strip() or "Unknown entity",
                entity_type=str(entity.entity_type or "").strip() or "topic",
                description=str(entity.description or "").strip() or None,
            )
            for entity in bundle.entities
            if str(entity.name or "").strip()
        ],
        open_questions=_clean_string_list(bundle.open_questions),
        risks=_clean_string_list(bundle.risks),
    )


def render_summary_markdown(bundle: StructuredSummaryBundle) -> str:
    action_items = (
        "\n".join(
            f"- {item.task}"
            + (f" (Owner: {item.owner})" if item.owner else "")
            + (f" [Due: {item.due_hint}]" if item.due_hint else "")
            for item in bundle.action_items
        )
        if bundle.action_items
        else "None stated"
    )
    open_questions = (
        "\n".join(f"- {question}" for question in bundle.open_questions)
        if bundle.open_questions
        else "None stated"
    )
    risks = (
        "\n".join(f"- {risk}" for risk in bundle.risks)
        if bundle.risks
        else "None stated"
    )
    key_points = (
        "\n".join(f"- {point}" for point in bundle.key_points)
        if bundle.key_points
        else "- No key points extracted."
    )

    return f"""# {bundle.headline}

## Overview
{bundle.overview}

## Key Points
{key_points}

## Action Items / Follow-ups
{action_items}

## Open Questions
{open_questions}

## Risks
{risks}
"""


def build_summary_variants(bundle: StructuredSummaryBundle) -> dict[str, Any]:
    return {
        "overview": bundle.overview,
        "key_points": bundle.key_points,
        "chapters": [chapter.model_dump() for chapter in bundle.chapters],
        "highlights": [highlight.model_dump() for highlight in bundle.highlights],
        "keywords": bundle.keywords,
        "action_items": [item.model_dump() for item in bundle.action_items],
        "entities": [entity.model_dump() for entity in bundle.entities],
        "open_questions": bundle.open_questions,
        "risks": bundle.risks,
    }


def generate_fallback_summary_bundle(
    transcript_text: str,
    *,
    content_profile: str | None = None,
) -> StructuredSummaryBundle:
    logger.warning("Using fallback summary generation method")
    preview = transcript_text[:500].strip()
    if len(transcript_text) > 500:
        preview += "..."

    word_count = len(transcript_text.split())
    reading_time = round(word_count / 150)
    profile = normalize_content_profile(content_profile)

    return StructuredSummaryBundle(
        content_profile=profile,
        headline="Transcript preview",
        overview=preview or "No transcript preview available.",
        key_points=[
            f"Word count: {word_count}",
            f"Estimated reading time: {reading_time} minute(s)",
            "LLM output was unavailable, so this is a fallback summary.",
        ],
        risks=[
            f"Full AI summary generation requires Ollama at {LLM_HOST} with model '{LLM_MODEL}'."
        ],
    )


def generate_summary_bundle(
    transcript_text: str,
    video_path: str,
    *,
    content_profile: str | None = None,
    transcript_segments: Sequence[dict[str, Any]] | None = None,
) -> StructuredSummaryBundle:
    basename = os.path.basename(video_path) or "Untitled media"
    normalized_profile = normalize_content_profile(content_profile)
    logger.info(
        "Generating structured summary for '%s' with content profile '%s'",
        basename,
        normalized_profile,
    )
    logger.info("Transcript length: %s characters", len(transcript_text))

    try:
        client = get_ollama_client()
        bundle = client.generate_json(
            build_structured_summary_prompt(
                transcript_text,
                title_hint=basename,
                content_profile=normalized_profile,
                transcript_segments=transcript_segments,
            ),
            response_model=StructuredSummaryBundle,
            temperature=0.2,
            max_tokens=max(SUMMARY_MAX_TOKENS, 2048),
        )
        normalized_bundle = normalize_summary_bundle(bundle)
        logger.info(
            "Structured summary generated successfully (%s key points, %s chapters)",
            len(normalized_bundle.key_points),
            len(normalized_bundle.chapters),
        )
        return normalized_bundle
    except Exception as error:
        logger.error("Error generating structured summary: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
        return generate_fallback_summary_bundle(
            transcript_text,
            content_profile=normalized_profile,
        )


def create_summary(
    transcript_text: str,
    video_path: str,
    *,
    content_profile: str | None = None,
) -> str:
    bundle = generate_summary_bundle(
        transcript_text,
        video_path,
        content_profile=content_profile,
    )
    return render_summary_markdown(bundle)


def summarize_from_file(transcript_path: str, video_path: str) -> str:
    logger.info("Summarizing from file: %s", transcript_path)
    try:
        with open(transcript_path) as file_handle:
            transcript_text = file_handle.read()
        return create_summary(transcript_text, video_path)
    except Exception as error:
        logger.error("Error reading transcript file: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
        return f"Error reading transcript file: {error}"
