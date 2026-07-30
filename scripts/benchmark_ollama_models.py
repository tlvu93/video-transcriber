#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "benchmarks"
SUMMARY_SECTION_PATTERNS = {
    "One-Sentence Overview": r"one[- ]sentence overview",
    "Participants": r"participants",
    "Key Topics Discussed": r"key topics discussed",
    "Decisions": r"decisions",
    "Action Items": r"action items",
    "Open Questions / Risks": r"open questions\s*/\s*risks",
    "Next Check-point": r"next check[- ]point",
}
LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
}
SUMMARY_PROMPT_TEMPLATE = """You are an expert meeting-minute writer.

TASK
Summarise the transcript that follows the line ---.

OBJECTIVES
• Detect the meeting's main topic(s) and label them (even if not explicit).
• Identify participants and replace pronouns with names where obvious.
• Capture only information that matters:
   – decisions made
   – action items (owner · task · due date if mentioned)
   – blockers / issues / risks
   – open questions
   – key data points (numbers, URLs, ticket IDs, etc.)
• Discard all filler (greetings, "can you see my screen", navigation clicks, jokes, repeated yes/no, etc.).

OUTPUT FORMAT (Markdown)
1. **One-Sentence Overview** – ≤ 30 words.
2. **Participants** – bullet list *Name (role/affiliation if clear)*.
3. **Key Topics Discussed** – bullets, ≤ 12 words each.
4. **Decisions** – bullets beginning with **✓**.
5. **Action Items** – bullets beginning with **→ Owner – Task – Due/When**.
6. **Open Questions / Risks** – bullets beginning with **?**.
7. **Next Check-point** – "No date mentioned" or the first future date heard.

CONSTRAINTS
• Maximum 120 words per section.
• If something is ambiguous, note it with "[unclear]".
• If a required element is completely missing, output "None stated".
• Before finalising, reread your draft and trim any stray filler or duplicate points.

---

{text}
"""
TRANSLATION_PROMPT_TEMPLATE = """You are a professional translator. \
Translate each string in the JSON array from {source_language_name} to {target_language_name}.

IMPORTANT RULES:
1. Return valid JSON only.
2. Return a JSON array of strings with the exact same number of items and the same order as the input.
3. Translate only the text content of each array entry.
4. Do not add commentary, markdown, code fences, or metadata.
5. Preserve speaker labels, timestamps, and special terminology when present in the text.

Input JSON:
{input_json}

Output JSON:"""


@dataclass
class TranscriptSample:
    source_label: str
    content: str
    segments: list[dict[str, Any]]
    transcript_id: str | None = None
    video_id: str | None = None
    language_code: str = "en"
    created_at: str | None = None


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def get_setting(name: str, dotenv_values: dict[str, str], default: str) -> str:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    value = dotenv_values.get(name, "")
    if value and value.strip():
        return value.strip()
    return default


def normalize_url(
    raw_url: str,
    *,
    default_port: int,
    default_path: str,
    docker_hostnames: set[str],
) -> str:
    parsed = parse.urlsplit(raw_url)
    scheme = parsed.scheme or "http"
    hostname = parsed.hostname or "localhost"
    if hostname in docker_hostnames or hostname in {"0.0.0.0", "127.0.0.1"}:
        hostname = "localhost"
    port = parsed.port or default_port
    path = parsed.path or default_path
    netloc = f"{hostname}:{port}"
    return parse.urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))


def parse_models(values: list[str] | None, default_model: str) -> list[str]:
    if not values:
        return [default_model]

    models: list[str] = []
    for value in values:
        for candidate in value.split(","):
            candidate = candidate.strip()
            if candidate and candidate not in models:
                models.append(candidate)

    return models or [default_model]


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "value"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def http_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> Any:
    data: bytes | None = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response received from {url}") from exc


def normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if not isinstance(raw_segments, list):
        return segments

    for index, raw_segment in enumerate(raw_segments, start=1):
        if isinstance(raw_segment, dict):
            text = str(raw_segment.get("text", "")).strip()
            if not text:
                continue
            segments.append(
                {
                    "id": raw_segment.get("id", index),
                    "text": text,
                    "speaker": raw_segment.get("speaker"),
                    "start": raw_segment.get("start", raw_segment.get("start_time")),
                    "end": raw_segment.get("end", raw_segment.get("end_time")),
                }
            )
        elif isinstance(raw_segment, str):
            text = raw_segment.strip()
            if text:
                segments.append({"id": index, "text": text, "speaker": None, "start": None, "end": None})

    return segments


def compose_content(content: str, segments: list[dict[str, Any]]) -> str:
    if content.strip():
        return content.strip()
    return "\n".join(segment["text"] for segment in segments if segment.get("text")).strip()


def sample_from_payload(payload: Any, source_label: str) -> TranscriptSample:
    if isinstance(payload, dict):
        segments = normalize_segments(payload.get("segments"))
        content = compose_content(str(payload.get("content", "")), segments)
        return TranscriptSample(
            source_label=source_label,
            content=content,
            segments=segments,
            transcript_id=payload.get("id"),
            video_id=payload.get("video_id"),
            language_code=str(payload.get("language_code") or payload.get("source_language") or "en"),
            created_at=payload.get("created_at"),
        )

    if isinstance(payload, list):
        segments = normalize_segments(payload)
        content = compose_content("", segments)
        return TranscriptSample(source_label=source_label, content=content, segments=segments)

    raise RuntimeError(f"Unsupported transcript payload in {source_label}")


def load_sample_from_file(path: Path) -> TranscriptSample:
    if not path.exists():
        raise RuntimeError(f"Input file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return sample_from_payload(json.loads(raw_text), str(path))

    return TranscriptSample(source_label=str(path), content=raw_text.strip(), segments=[])


def parse_created_at(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


def fetch_latest_transcript(api_url: str) -> TranscriptSample:
    transcripts = http_json(f"{api_url.rstrip('/')}/transcripts/")
    if not isinstance(transcripts, list) or not transcripts:
        raise RuntimeError("No transcripts found via the API")

    latest = max(transcripts, key=lambda item: parse_created_at(item.get("created_at")))
    return sample_from_payload(latest, f"{api_url}/transcripts/{latest.get('id', 'latest')}")


def fetch_transcript_by_id(api_url: str, transcript_id: str) -> TranscriptSample:
    payload = http_json(f"{api_url.rstrip('/')}/transcripts/{transcript_id}")
    return sample_from_payload(payload, f"{api_url}/transcripts/{transcript_id}")


def build_summary_input(sample: TranscriptSample, max_chars: int) -> tuple[str, bool]:
    content = sample.content.strip()
    if max_chars <= 0 or len(content) <= max_chars:
        return content, False

    window = content[:max_chars]
    trim_index = window.rfind(" ")
    if trim_index >= int(max_chars * 0.8):
        window = window[:trim_index]
    return window.rstrip() + "\n\n[Transcript truncated for benchmark]", True


def split_text_chunks(text: str, *, max_chunk_chars: int) -> list[str]:
    chunks: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    sentence_splitter = re.compile(r"(?<=[.!?])\s+")

    for paragraph in paragraphs:
        if len(paragraph) <= max_chunk_chars:
            chunks.append(paragraph)
            continue

        current = ""
        for sentence in sentence_splitter.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not current:
                current = sentence
                continue
            if len(current) + 1 + len(sentence) <= max_chunk_chars:
                current = f"{current} {sentence}"
            else:
                chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

    if not chunks and text.strip():
        chunks.append(text.strip()[:max_chunk_chars])

    return chunks


def build_translation_items(
    sample: TranscriptSample,
    *,
    max_items: int,
    max_chars: int,
) -> list[str]:
    candidates = [segment["text"].strip() for segment in sample.segments if segment.get("text")]
    if not candidates:
        candidates = split_text_chunks(sample.content, max_chunk_chars=min(700, max_chars))

    items: list[str] = []
    used_chars = 0
    for candidate in candidates:
        if not candidate:
            continue
        text = candidate
        if not items and len(text) > max_chars:
            text = text[:max_chars].rstrip()
        if items and (len(items) >= max_items or used_chars + len(text) > max_chars):
            break
        items.append(text)
        used_chars += len(text)
        if len(items) >= max_items:
            break

    return items


def strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def call_ollama(
    ollama_url: str,
    *,
    model: str,
    prompt: str,
    num_predict: int,
) -> tuple[str, dict[str, Any], float]:
    started_at = time.perf_counter()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": num_predict,
        },
    }
    response = http_json(ollama_url, payload=payload, timeout_seconds=900)
    wall_time_seconds = time.perf_counter() - started_at
    output = strip_think_tags(str(response.get("response", "")))
    if not output:
        raise RuntimeError(f"Ollama returned an empty response for model {model}")
    return output, response, wall_time_seconds


def extract_json_array(response_text: str) -> list[str]:
    response_text = response_text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
    if fenced_match:
        response_text = fenced_match.group(1).strip()

    start_index = response_text.find("[")
    end_index = response_text.rfind("]")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("Response did not contain a JSON array")

    candidate = response_text[start_index : end_index + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Response did not contain a string array")
    return parsed


def evaluate_summary_output(output_text: str) -> dict[str, Any]:
    found = []
    missing = []
    for label, pattern in SUMMARY_SECTION_PATTERNS.items():
        if re.search(pattern, output_text, flags=re.IGNORECASE):
            found.append(label)
        else:
            missing.append(label)

    return {
        "output_chars": len(output_text),
        "output_words": len(output_text.split()),
        "section_count": len(found),
        "sections_found": found,
        "sections_missing": missing,
    }


def evaluate_translation_output(output_text: str, expected_items: int) -> dict[str, Any]:
    try:
        parsed_items = extract_json_array(output_text)
        return {
            "valid_json": True,
            "item_count_matches": len(parsed_items) == expected_items,
            "output_item_count": len(parsed_items),
            "nonempty_items": sum(1 for item in parsed_items if item.strip()),
            "preview_items": parsed_items[:2],
        }
    except Exception as exc:
        return {
            "valid_json": False,
            "item_count_matches": False,
            "output_item_count": 0,
            "nonempty_items": 0,
            "preview_items": [],
            "parse_error": str(exc),
        }


def safe_ollama_duration_seconds(response_payload: dict[str, Any]) -> float | None:
    duration = response_payload.get("total_duration")
    if isinstance(duration, int):
        return duration / 1_000_000_000
    return None


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    successful_runs = [run for run in runs if run["success"]]
    if not successful_runs:
        return {
            "success": False,
            "repeat_count": len(runs),
            "successful_runs": 0,
            "failed_runs": len(runs),
        }

    wall_times = [run["wall_time_seconds"] for run in successful_runs]
    ollama_times = [
        run["ollama_duration_seconds"]
        for run in successful_runs
        if run.get("ollama_duration_seconds") is not None
    ]
    summary: dict[str, Any] = {
        "success": True,
        "repeat_count": len(runs),
        "successful_runs": len(successful_runs),
        "failed_runs": len(runs) - len(successful_runs),
        "wall_time_seconds_avg": round(sum(wall_times) / len(wall_times), 3),
        "wall_time_seconds_min": round(min(wall_times), 3),
        "wall_time_seconds_max": round(max(wall_times), 3),
    }
    if ollama_times:
        summary["ollama_duration_seconds_avg"] = round(sum(ollama_times) / len(ollama_times), 3)
    return summary


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def benchmark_summaries(
    models: list[str],
    *,
    ollama_url: str,
    repeat_count: int,
    run_dir: Path,
    sample: TranscriptSample,
    max_chars: int,
) -> list[dict[str, Any]]:
    prompt_input, truncated = build_summary_input(sample, max_chars)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(text=prompt_input)
    write_text(run_dir / "inputs" / "summary_input.txt", prompt_input)

    results: list[dict[str, Any]] = []
    for model in models:
        model_slug = slugify(model)
        runs: list[dict[str, Any]] = []
        for attempt in range(1, repeat_count + 1):
            try:
                output_text, response_payload, wall_time_seconds = call_ollama(
                    ollama_url,
                    model=model,
                    prompt=prompt,
                    num_predict=1024,
                )
                write_text(
                    run_dir / "outputs" / f"summary-{model_slug}-run{attempt}.md",
                    output_text,
                )
                evaluation = evaluate_summary_output(output_text)
                runs.append(
                    {
                        "attempt": attempt,
                        "success": True,
                        "wall_time_seconds": round(wall_time_seconds, 3),
                        "ollama_duration_seconds": safe_ollama_duration_seconds(response_payload),
                        "evaluation": evaluation,
                        "output_path": display_path(run_dir / "outputs" / f"summary-{model_slug}-run{attempt}.md"),
                    }
                )
            except Exception as exc:
                runs.append(
                    {
                        "attempt": attempt,
                        "success": False,
                        "error": str(exc),
                    }
                )

        result = {
            "task": "summary",
            "model": model,
            "input_chars": len(prompt_input),
            "input_truncated": truncated,
            "runs": runs,
            "aggregate": summarize_runs(runs),
        }
        successful_runs = [run for run in runs if run["success"]]
        if successful_runs:
            result["best_preview"] = successful_runs[0]["evaluation"]
        results.append(result)

    return results


def benchmark_translations(
    models: list[str],
    *,
    ollama_url: str,
    repeat_count: int,
    run_dir: Path,
    sample: TranscriptSample,
    source_language: str,
    target_language: str,
    max_items: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    translation_items = build_translation_items(sample, max_items=max_items, max_chars=max_chars)
    if not translation_items:
        raise RuntimeError("Could not build translation benchmark items from the selected transcript")

    source_language_name = LANGUAGE_NAMES.get(source_language, source_language)
    target_language_name = LANGUAGE_NAMES.get(target_language, target_language)
    input_json = json.dumps(translation_items, ensure_ascii=False)
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(
        source_language_name=source_language_name,
        target_language_name=target_language_name,
        input_json=input_json,
    )
    write_json(run_dir / "inputs" / "translation_items.json", translation_items)

    results: list[dict[str, Any]] = []
    for model in models:
        model_slug = slugify(model)
        runs: list[dict[str, Any]] = []
        for attempt in range(1, repeat_count + 1):
            try:
                output_text, response_payload, wall_time_seconds = call_ollama(
                    ollama_url,
                    model=model,
                    prompt=prompt,
                    num_predict=2048,
                )
                evaluation = evaluate_translation_output(output_text, len(translation_items))
                output_path = run_dir / "outputs" / f"translation-{model_slug}-run{attempt}.txt"
                write_text(output_path, output_text)
                if evaluation["valid_json"]:
                    parsed_items = extract_json_array(output_text)
                    write_json(run_dir / "outputs" / f"translation-{model_slug}-run{attempt}.json", parsed_items)
                runs.append(
                    {
                        "attempt": attempt,
                        "success": True,
                        "wall_time_seconds": round(wall_time_seconds, 3),
                        "ollama_duration_seconds": safe_ollama_duration_seconds(response_payload),
                        "evaluation": evaluation,
                        "output_path": display_path(output_path),
                    }
                )
            except Exception as exc:
                runs.append(
                    {
                        "attempt": attempt,
                        "success": False,
                        "error": str(exc),
                    }
                )

        result = {
            "task": "translation",
            "model": model,
            "input_item_count": len(translation_items),
            "input_chars": sum(len(item) for item in translation_items),
            "source_language": source_language,
            "target_language": target_language,
            "runs": runs,
            "aggregate": summarize_runs(runs),
        }
        successful_runs = [run for run in runs if run["success"]]
        if successful_runs:
            result["best_preview"] = successful_runs[0]["evaluation"]
        results.append(result)

    return results


def render_task_lines(results: list[dict[str, Any]], task_name: str) -> list[str]:
    lines = [f"## {task_name}", ""]
    if not results:
        lines.extend(["No models were benchmarked for this task.", ""])
        return lines

    for result in results:
        aggregate = result["aggregate"]
        status = "ok" if aggregate["success"] else "failed"
        lines.append(f"- `{result['model']}`: {status}")
        if aggregate["success"]:
            lines.append(
                f"  avg wall time {aggregate['wall_time_seconds_avg']}s "
                f"({aggregate['successful_runs']}/{aggregate['repeat_count']} successful runs)"
            )
            preview = result.get("best_preview", {})
            if result["task"] == "summary":
                lines.append(
                    f"  sections found {preview.get('section_count', 0)}/"
                    f"{len(SUMMARY_SECTION_PATTERNS)}"
                )
            if result["task"] == "translation":
                lines.append(
                    f"  valid json={preview.get('valid_json', False)} "
                    f"item match={preview.get('item_count_matches', False)}"
                )
        else:
            first_error = next((run.get("error") for run in result["runs"] if run.get("error")), "unknown error")
            lines.append(f"  error: {first_error}")
        lines.append("")

    return lines


def build_markdown_report(
    *,
    sample: TranscriptSample,
    summary_results: list[dict[str, Any]],
    translation_results: list[dict[str, Any]],
    run_dir: Path,
    ollama_url: str,
    api_url: str | None,
    repeat_count: int,
) -> str:
    lines = [
        "# Model Benchmark",
        "",
        f"- Generated at: {datetime.now(UTC).isoformat()}",
        f"- Output directory: `{display_path(run_dir)}`",
        f"- Sample source: `{sample.source_label}`",
        f"- Transcript ID: `{sample.transcript_id or 'n/a'}`",
        f"- Video ID: `{sample.video_id or 'n/a'}`",
        f"- Source language: `{sample.language_code}`",
        f"- Transcript chars: `{len(sample.content)}`",
        f"- Segment count: `{len(sample.segments)}`",
        f"- Ollama URL: `{ollama_url}`",
        f"- API URL: `{api_url or 'n/a'}`",
        f"- Repeat count: `{repeat_count}`",
        "",
    ]
    lines.extend(render_task_lines(summary_results, "Summarization"))
    lines.extend(render_task_lines(translation_results, "Translation"))
    return "\n".join(lines).strip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local Ollama models for transcript summarization and translation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python3 scripts/benchmark_ollama_models.py --latest-transcript
              python3 scripts/benchmark_ollama_models.py --input /path/to/transcript.json \\
                  --summary-model mistral-small3.1 --summary-model qwen3:14b
              python3 scripts/benchmark_ollama_models.py --transcript-id 123 --task translation \\
                  --translation-model qwen3:14b --translation-model deepseek-r1 --target-language de
            """
        ),
    )
    parser.add_argument("--task", choices=["both", "summary", "translation"], default="both")
    parser.add_argument("--input", type=Path, help="Transcript text file or transcript JSON payload")
    parser.add_argument("--transcript-id", help="Transcript ID to fetch from the local API")
    parser.add_argument(
        "--latest-transcript",
        action="store_true",
        help="Fetch the latest transcript from the local API",
    )
    parser.add_argument("--api-url", help="Override the API base URL used for transcript lookup")
    parser.add_argument("--ollama-url", help="Override the Ollama generate URL")
    parser.add_argument("--summary-model", action="append", help="Summary model(s), repeat or comma-separate")
    parser.add_argument("--translation-model", action="append", help="Translation model(s), repeat or comma-separate")
    parser.add_argument("--source-language", help="Force the source language code")
    parser.add_argument("--target-language", default="de", help="Translation target language code")
    parser.add_argument("--summary-max-chars", type=int, default=20000)
    parser.add_argument("--translation-max-items", type=int, default=8)
    parser.add_argument("--translation-max-chars", type=int, default=6000)
    parser.add_argument("--repeat", type=int, default=1, help="Number of runs per model")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    dotenv_values = load_env_file(REPO_ROOT / ".env")

    default_api_port = int(get_setting("API_PORT", dotenv_values, "8000"))
    default_ollama_port = int(get_setting("OLLAMA_PORT", dotenv_values, "11434"))
    default_api_url = normalize_url(
        get_setting("API_URL", dotenv_values, f"http://localhost:{default_api_port}"),
        default_port=default_api_port,
        default_path="",
        docker_hostnames={"api"},
    ).rstrip("/")
    default_ollama_url = normalize_url(
        get_setting("LLM_HOST", dotenv_values, f"http://localhost:{default_ollama_port}/api/generate"),
        default_port=default_ollama_port,
        default_path="/api/generate",
        docker_hostnames={"ollama"},
    )

    summary_default = get_setting("SUMMARIZATION_LLM_MODEL", dotenv_values, "mistral-small3.1")
    translation_default = get_setting("TRANSLATION_LLM_MODEL", dotenv_values, "qwen3:14b")
    summary_models = parse_models(args.summary_model, summary_default)
    translation_models = parse_models(args.translation_model, translation_default)

    api_url = args.api_url.rstrip("/") if args.api_url else default_api_url
    ollama_url = args.ollama_url or default_ollama_url

    try:
        if args.input:
            sample = load_sample_from_file(args.input)
        elif args.transcript_id:
            sample = fetch_transcript_by_id(api_url, args.transcript_id)
        else:
            sample = fetch_latest_transcript(api_url)
    except Exception as exc:
        print(f"Failed to load a transcript sample: {exc}", file=sys.stderr)
        print(
            "Tip: pass --input /path/to/transcript.json or start the API and use --latest-transcript.",
            file=sys.stderr,
        )
        return 1

    sample.language_code = args.source_language or sample.language_code or "en"
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    sample_slug = slugify(sample.transcript_id or Path(sample.source_label).stem or "transcript")
    run_dir = args.output_dir / f"{run_id}-{sample_slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "sample.json", asdict(sample))

    summary_results: list[dict[str, Any]] = []
    translation_results: list[dict[str, Any]] = []
    if args.task in {"both", "summary"}:
        summary_results = benchmark_summaries(
            summary_models,
            ollama_url=ollama_url,
            repeat_count=max(1, args.repeat),
            run_dir=run_dir,
            sample=sample,
            max_chars=max(0, args.summary_max_chars),
        )
    if args.task in {"both", "translation"}:
        translation_results = benchmark_translations(
            translation_models,
            ollama_url=ollama_url,
            repeat_count=max(1, args.repeat),
            run_dir=run_dir,
            sample=sample,
            source_language=sample.language_code,
            target_language=args.target_language,
            max_items=max(1, args.translation_max_items),
            max_chars=max(256, args.translation_max_chars),
        )

    report_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_directory": str(run_dir),
        "sample": asdict(sample),
        "ollama_url": ollama_url,
        "api_url": api_url,
        "summary_models": summary_models,
        "translation_models": translation_models,
        "repeat_count": max(1, args.repeat),
        "summary_results": summary_results,
        "translation_results": translation_results,
    }
    markdown_report = build_markdown_report(
        sample=sample,
        summary_results=summary_results,
        translation_results=translation_results,
        run_dir=run_dir,
        ollama_url=ollama_url,
        api_url=api_url,
        repeat_count=max(1, args.repeat),
    )
    write_json(run_dir / "report.json", report_payload)
    write_text(run_dir / "report.md", markdown_report)

    print(f"Benchmark complete. Report: {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
