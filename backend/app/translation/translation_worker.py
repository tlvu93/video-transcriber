import logging
import time
import traceback
from typing import Any

from backend.app.domain.jobs import (
    JobCancellationRequestedError,
    claim_next_translation_job,
    complete_translation_job,
    ensure_translation_job_not_cancelled,
    fail_translation_job,
    get_translation_job,
    heartbeat_translation_job,
    update_translation_job_progress,
)
from backend.app.domain.records import create_or_update_translated_transcript, get_transcript
from backend.app.runtime.metrics import record_metric_event
from backend.app.translation.cache import (
    compute_translation_cache_key,
    read_cached_translation,
    write_cached_translation,
)
from backend.app.translation.translator import detect_language, translate_segments, translate_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translation.worker")
SUBTITLE_QA_MAX_CHARS_PER_LINE = 42
SUBTITLE_QA_MAX_CHARS_PER_SECOND = 20.0


def build_translated_content_from_segments(
    translated_segments: list | None, fallback_content: str
) -> str:
    if not translated_segments:
        return fallback_content

    segment_texts = [
        str(segment.get("text", "")).strip()
        for segment in translated_segments
        if str(segment.get("text", "")).strip()
    ]

    if not segment_texts:
        return fallback_content

    return " ".join(segment_texts)


def compute_subtitle_qa_metrics(
    translated_segments: list[dict[str, Any]] | None,
    source_segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    segments = translated_segments or []
    source_segments = source_segments or []
    overlap_warnings = 0
    long_line_warnings = 0
    high_cps_warnings = 0
    missing_speaker_warnings = 0
    previous_end = None

    for index, segment in enumerate(segments):
        text = str(segment.get("text", "")).strip()
        duration = float(segment.get("end_time", 0) or 0) - float(
            segment.get("start_time", 0) or 0
        )

        if text and len(text) > SUBTITLE_QA_MAX_CHARS_PER_LINE:
            long_line_warnings += 1

        if text and duration > 0:
            characters_per_second = len(text) / duration
            if characters_per_second > SUBTITLE_QA_MAX_CHARS_PER_SECOND:
                high_cps_warnings += 1

        start_time = float(segment.get("start_time", 0) or 0)
        if previous_end is not None and start_time < previous_end:
            overlap_warnings += 1

        previous_end = float(segment.get("end_time", 0) or 0)
        source_segment = source_segments[index] if index < len(source_segments) else None
        source_speaker = source_segment.get("speaker") if isinstance(source_segment, dict) else None
        if source_speaker and not segment.get("speaker"):
            missing_speaker_warnings += 1

    return {
        "segment_count": len(segments),
        "long_line_warnings": long_line_warnings,
        "high_cps_warnings": high_cps_warnings,
        "overlap_warnings": overlap_warnings,
        "missing_speaker_warnings": missing_speaker_warnings,
        "max_chars_per_line": SUBTITLE_QA_MAX_CHARS_PER_LINE,
        "max_chars_per_second": SUBTITLE_QA_MAX_CHARS_PER_SECOND,
    }


def get_job_from_api(job_id: str) -> dict[str, Any]:
    return get_translation_job(job_id)


def get_transcript_from_api(transcript_id: str) -> dict[str, Any]:
    return get_transcript(transcript_id)


def create_translation_api(
    transcript_id: str,
    language: str,
    content: str,
    segments: list | None = None,
    *,
    style_guide: str | None = None,
    glossary_terms: list[dict[str, str]] | None = None,
    qa_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    translation = create_or_update_translated_transcript(
        transcript_id,
        language,
        content,
        segments=segments,
        style_guide=style_guide,
        glossary_terms=glossary_terms,
        qa_metrics=qa_metrics,
    )
    logger.info("Translation created for transcript %s in language %s", transcript_id, language)
    return translation


def update_job_status_api(
    job_id: str,
    worker_id: str,
    status: str,
    processing_time: float | None = None,
    error_details: dict[str, Any] | None = None,
) -> None:
    try:
        if status == "completed":
            complete_translation_job(
                job_id,
                worker_id,
                processing_time=processing_time,
                error_details=error_details,
            )
        elif status == "failed":
            fail_translation_job(
                job_id,
                worker_id,
                error_details=error_details or {"error": "Unknown error"},
            )
        else:
            raise ValueError(f"Unsupported translation job status transition: {status}")

        logger.info("Updated translation job %s status to %s", job_id, status)
    except Exception as error:
        logger.error("Error updating translation job %s: %s", job_id, error)
        logger.error("Exception traceback: %s", traceback.format_exc())


def claim_next_translation_job_api(worker_id: str) -> dict[str, Any] | None:
    return claim_next_translation_job(worker_id)


def heartbeat_translation_job_api(job_id: str, worker_id: str) -> None:
    heartbeat_translation_job(job_id, worker_id)


def update_translation_job_progress_api(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: dict[str, Any] | None = None,
) -> None:
    update_translation_job_progress(
        job_id,
        worker_id,
        progress,
        error_details=error_details,
    )


def ensure_translation_job_not_cancelled_api(job_id: str, worker_id: str) -> None:
    ensure_translation_job_not_cancelled(job_id, worker_id)


def process_translation_job(job_id: str, worker_id: str) -> bool:
    start_time = time.time()
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        timings: dict[str, Any] = {}
        try:
            job_fetch_started_at = time.perf_counter()
            job = get_job_from_api(job_id)
            transcript_id = job["transcript_id"]
            target_language = job["target_language"]
            style_guide = job.get("style_guide")
            glossary_terms = job.get("glossary_terms") or []
            timings["job_fetch_seconds"] = round(time.perf_counter() - job_fetch_started_at, 3)
            timings["target_language"] = target_language
            timings["style_guide_used"] = bool(style_guide)
            timings["glossary_term_count"] = len(glossary_terms)
            update_translation_job_progress_api(job_id, worker_id, 0.05)
            ensure_translation_job_not_cancelled_api(job_id, worker_id)

            transcript_fetch_started_at = time.perf_counter()
            transcript = get_transcript_from_api(transcript_id)
            if not transcript:
                error_details = {"error": f"Transcript not found: {transcript_id}"}
                update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
                return False
            timings["transcript_fetch_seconds"] = round(
                time.perf_counter() - transcript_fetch_started_at,
                3,
            )
            update_translation_job_progress_api(job_id, worker_id, 0.15)
            ensure_translation_job_not_cancelled_api(job_id, worker_id)

            transcript_content = transcript["content"]
            transcript_segments = transcript.get("segments", [])
            timings["input_characters"] = len(transcript_content or "")
            timings["segment_count"] = len(transcript_segments or [])

            source_language = transcript.get("language_code") or job.get("source_language")
            if not source_language:
                logger.info("No source language specified, attempting to detect...")
                language_detect_started_at = time.perf_counter()
                source_language = detect_language(transcript_content)
                timings["language_detection_seconds"] = round(
                    time.perf_counter() - language_detect_started_at,
                    3,
                )
                logger.info("Detected source language: %s", source_language)
            else:
                timings["language_detection_seconds"] = 0.0
                logger.info("Using source language from transcript: %s", source_language)
            timings["source_language"] = source_language
            update_translation_job_progress_api(job_id, worker_id, 0.25)
            ensure_translation_job_not_cancelled_api(job_id, worker_id)

            cache_lookup_started_at = time.perf_counter()
            cache_key = compute_translation_cache_key(
                transcript_content,
                transcript_segments,
                source_language,
                target_language,
            )
            cached_translation = read_cached_translation(cache_key)
            timings["cache_key_prefix"] = cache_key[:12]
            timings["cache_lookup_seconds"] = round(
                time.perf_counter() - cache_lookup_started_at,
                3,
            )
            timings["cache_hit"] = cached_translation is not None
            update_translation_job_progress_api(job_id, worker_id, 0.35)
            ensure_translation_job_not_cancelled_api(job_id, worker_id)

            if cached_translation:
                logger.info(
                    "Reusing cached translation for transcript %s from %s to %s",
                    transcript_id,
                    source_language,
                    target_language,
                )
                translated_content = cached_translation.get("content", transcript_content)
                translated_segments = cached_translation.get("segments")
                timings["translation_strategy"] = "cache_hit"
                timings["translation_seconds"] = 0.0
                update_translation_job_progress_api(job_id, worker_id, 0.7)
            else:
                translation_started_at = time.perf_counter()
                if source_language == target_language:
                    logger.info(
                        "Source and target languages are the same (%s), creating copy",
                        source_language,
                    )
                    translated_content = transcript_content
                    translated_segments = transcript_segments
                    timings["translation_strategy"] = "copy"
                else:
                    logger.info(
                        "Translating transcript %s from %s to %s",
                        transcript_id,
                        source_language,
                        target_language,
                    )
                    if transcript_segments:
                        translated_segments = translate_segments(
                            transcript_segments,
                            source_language,
                            target_language,
                            style_guide=style_guide,
                            glossary_terms=glossary_terms,
                        )
                        translated_content = build_translated_content_from_segments(
                            translated_segments,
                            transcript_content,
                        )
                        timings["translation_strategy"] = "segment_batches"
                    else:
                        translated_content = translate_text(
                            transcript_content,
                            source_language,
                            target_language,
                            style_guide=style_guide,
                            glossary_terms=glossary_terms,
                        )
                        translated_segments = None
                        timings["translation_strategy"] = "full_content"

                    if translated_content == transcript_content and source_language != target_language:
                        logger.warning(
                            "Translation returned original text, this might indicate a translation failure"
                        )
                timings["translation_seconds"] = round(
                    time.perf_counter() - translation_started_at,
                    3,
                )
                update_translation_job_progress_api(job_id, worker_id, 0.7)
                ensure_translation_job_not_cancelled_api(job_id, worker_id)

                cache_write_started_at = time.perf_counter()
                write_cached_translation(
                    cache_key,
                    content=translated_content,
                    segments=translated_segments,
                    source_language=source_language,
                    target_language=target_language,
                    strategy=timings["translation_strategy"],
                )
                timings["cache_write_seconds"] = round(
                    time.perf_counter() - cache_write_started_at,
                    3,
                )
            timings["output_characters"] = len(translated_content or "")
            qa_metrics = compute_subtitle_qa_metrics(
                translated_segments,
                source_segments=transcript_segments,
            )
            timings["qa_metrics"] = qa_metrics
            update_translation_job_progress_api(job_id, worker_id, 0.85)
            ensure_translation_job_not_cancelled_api(job_id, worker_id)

            persist_started_at = time.perf_counter()
            create_translation_api(
                transcript_id,
                target_language,
                translated_content,
                translated_segments,
                style_guide=style_guide,
                glossary_terms=glossary_terms,
                qa_metrics=qa_metrics,
            )
            timings["persist_seconds"] = round(time.perf_counter() - persist_started_at, 3)
            update_translation_job_progress_api(job_id, worker_id, 0.95)

            processing_time = time.time() - start_time
            timings["total_processing_seconds"] = round(processing_time, 3)
            update_job_status_api(
                job_id,
                worker_id,
                "completed",
                processing_time=processing_time,
                error_details={"metrics": timings},
            )
            record_metric_event(
                "translation_time_seconds",
                processing_time,
                source="translation_worker",
                labels={"target_language": target_language},
            )
            record_metric_event(
                "translation_cache_requests_total",
                1,
                source="translation_worker",
                labels={"cache_hit": str(bool(cached_translation)).lower()},
            )

            logger.info(
                "Translation completed for transcript %s in %.2f seconds with metrics: %s",
                transcript_id,
                processing_time,
                timings,
            )
            return True

        except JobCancellationRequestedError:
            logger.info("Cancellation requested for translation job %s", job_id)
            processing_time = time.time() - start_time
            complete_translation_job(
                job_id,
                worker_id,
                processing_time=processing_time,
                error_details={"error": "Job cancelled by request", "metrics": timings},
            )
            return False
        except Exception as error:
            retry_count += 1
            logger.error(
                "Error processing translation job %s (attempt %s/%s): %s",
                job_id,
                retry_count,
                max_retries,
                error,
            )

            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.info("Retrying in %s seconds...", wait_time)
                time.sleep(wait_time)
            else:
                logger.error("All retry attempts failed for job %s", job_id)
                logger.error("Exception traceback: %s", traceback.format_exc())
                error_details = {
                    "error": str(error),
                    "traceback": traceback.format_exc()[:1000],
                    "retry_count": retry_count,
                    "metrics": timings,
                }
                update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
                return False

    return False
