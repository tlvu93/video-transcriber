#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_TEXT = (
    "Hello from the video transcriber smoke test. "
    "This short sample verifies upload, transcription, summarization, and translation. "
    "Please capture this message clearly."
)
DEFAULT_TARGET_LANGUAGE = "de"
POLL_INTERVAL_SECONDS = float(os.environ.get("E2E_SMOKE_POLL_INTERVAL_SECONDS", "5"))
TRANSCRIPTION_TIMEOUT_SECONDS = int(os.environ.get("E2E_SMOKE_TRANSCRIPTION_TIMEOUT_SECONDS", "900"))
SUMMARIZATION_TIMEOUT_SECONDS = int(os.environ.get("E2E_SMOKE_SUMMARIZATION_TIMEOUT_SECONDS", "900"))
TRANSLATION_TIMEOUT_SECONDS = int(os.environ.get("E2E_SMOKE_TRANSLATION_TIMEOUT_SECONDS", "900"))
JOB_CREATION_TIMEOUT_SECONDS = int(os.environ.get("E2E_SMOKE_JOB_CREATION_TIMEOUT_SECONDS", "120"))


def log(message: str) -> None:
    print(message, flush=True)


def api_base_url() -> str:
    return os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")


def build_url(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    url = f"{api_base_url()}/{path.lstrip('/')}"
    if params:
        query = urlencode(
            {key: value for key, value in params.items() if value is not None},
            doseq=True,
        )
        if query:
            url = f"{url}?{query}"
    return url


def run_command(command: list[str], description: str) -> str:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"Failed to {description}: {details}")
    return result.stdout


def request_json(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        build_url(path, params=params),
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {request.full_url} failed with {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"{method} {request.full_url} failed: {error}") from error


def create_sample_video(temp_dir: Path) -> Path:
    configured_sample = os.environ.get("E2E_SMOKE_SAMPLE_VIDEO")
    if configured_sample:
        sample_path = Path(configured_sample).expanduser().resolve()
        if not sample_path.exists():
            raise RuntimeError(f"E2E_SMOKE_SAMPLE_VIDEO does not exist: {sample_path}")
        log(f"Using configured sample video: {sample_path}")
        return sample_path

    say_binary = shutil.which("say")
    ffmpeg_binary = shutil.which("ffmpeg")
    if not say_binary or not ffmpeg_binary:
        raise RuntimeError(
            "Generating a smoke sample requires both 'say' and 'ffmpeg'. "
            "Set E2E_SMOKE_SAMPLE_VIDEO to use an existing clip instead."
        )

    sample_text = os.environ.get("E2E_SMOKE_SAMPLE_TEXT", DEFAULT_SAMPLE_TEXT)
    sample_voice = os.environ.get("E2E_SMOKE_SAMPLE_VOICE", "").strip()
    audio_path = temp_dir / "smoke-sample.aiff"
    video_path = temp_dir / "video-transcriber-e2e-smoke.mp4"

    say_command = [say_binary, "-o", str(audio_path)]
    if sample_voice:
        say_command.extend(["-v", sample_voice])
    say_command.append(sample_text)
    run_command(say_command, "generate spoken smoke sample")

    ffmpeg_command = [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=640x360:r=24",
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(video_path),
    ]
    run_command(ffmpeg_command, "mux the smoke sample video")

    log(f"Generated smoke sample video: {video_path}")
    return video_path


def upload_video(video_path: Path) -> Dict[str, Any]:
    upload_url = build_url("/videos/")
    output = run_command(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "-X",
            "POST",
            "-F",
            f"file=@{video_path};type=video/mp4",
            upload_url,
        ],
        "upload the smoke sample video",
    )
    response = json.loads(output)
    log(f"Uploaded video {response['filename']} as video_id={response['id']}")
    return response


def wait_for_item(
    description: str,
    path: str,
    *,
    params: Dict[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = request_json("GET", path, params=params)
        items = response.get("items", [])
        if items:
            item = items[0]
            item_id = item.get("id", "<unknown>")
            log(f"{description} found: {item_id}")
            return item
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out waiting for {description}")


def wait_for_job_completion(
    description: str,
    path: str,
    job_id: str,
    *,
    timeout_seconds: int,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        job = request_json("GET", f"{path}/{job_id}")
        status = job.get("status")
        if status != last_status:
            log(f"{description} status: {status}")
            last_status = status

        if status == "completed":
            return job
        if status in {"failed", "cancelled"}:
            error_details = job.get("error_details")
            raise RuntimeError(f"{description} ended with status {status}: {error_details}")

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Timed out waiting for {description} to complete")


def verify_text_field(description: str, payload: Dict[str, Any], field_name: str = "content") -> None:
    content = str(payload.get(field_name, "")).strip()
    if not content:
        raise RuntimeError(f"{description} is missing '{field_name}' content")


def create_translation_job(transcript_id: str, target_language: str) -> Dict[str, Any]:
    payload = {
        "transcript_id": transcript_id,
        "target_language": target_language,
    }
    response = request_json("POST", "/translation-jobs/", payload=payload)
    log(f"Created translation job {response['id']} for transcript_id={transcript_id} -> {target_language}")
    return response


def main() -> int:
    target_language = os.environ.get("E2E_SMOKE_TARGET_LANGUAGE", DEFAULT_TARGET_LANGUAGE)
    with tempfile.TemporaryDirectory(prefix="video-transcriber-e2e-smoke-") as temp_dir:
        sample_video_path = create_sample_video(Path(temp_dir))
        video = upload_video(sample_video_path)
        video_id = video["id"]

        transcription_job = wait_for_item(
            "transcription job",
            "/transcription-jobs",
            params={"video_id": video_id, "limit": 1, "offset": 0},
            timeout_seconds=JOB_CREATION_TIMEOUT_SECONDS,
        )
        wait_for_job_completion(
            "transcription job",
            "/transcription-jobs",
            transcription_job["id"],
            timeout_seconds=TRANSCRIPTION_TIMEOUT_SECONDS,
        )

        transcript = wait_for_item(
            "transcript",
            "/transcripts/",
            params={"video_id": video_id, "limit": 1, "offset": 0},
            timeout_seconds=JOB_CREATION_TIMEOUT_SECONDS,
        )
        verify_text_field("Transcript", transcript)
        transcript_id = transcript["id"]
        log(f"Transcript created: transcript_id={transcript_id}")

        summarization_job = wait_for_item(
            "summarization job",
            "/summarization-jobs",
            params={"transcript_id": transcript_id, "limit": 1, "offset": 0},
            timeout_seconds=JOB_CREATION_TIMEOUT_SECONDS,
        )
        wait_for_job_completion(
            "summarization job",
            "/summarization-jobs",
            summarization_job["id"],
            timeout_seconds=SUMMARIZATION_TIMEOUT_SECONDS,
        )

        summary = wait_for_item(
            "summary",
            "/summaries/",
            params={"transcript_id": transcript_id, "limit": 1, "offset": 0},
            timeout_seconds=JOB_CREATION_TIMEOUT_SECONDS,
        )
        verify_text_field("Summary", summary)
        log(f"Summary created: summary_id={summary['id']}")

        translation_job = create_translation_job(transcript_id, target_language)
        wait_for_job_completion(
            "translation job",
            "/translation-jobs",
            translation_job["id"],
            timeout_seconds=TRANSLATION_TIMEOUT_SECONDS,
        )

        translated_transcript = wait_for_item(
            "translated transcript",
            "/translated-transcripts/",
            params={
                "transcript_id": transcript_id,
                "language": target_language,
                "limit": 1,
                "offset": 0,
            },
            timeout_seconds=JOB_CREATION_TIMEOUT_SECONDS,
        )
        verify_text_field("Translated transcript", translated_transcript)
        log(
            "Translation created: translated_transcript_id="
            f"{translated_transcript['id']} language={translated_transcript['language']}"
        )

        log(
            "E2E smoke checks passed for "
            f"video_id={video_id}, transcript_id={transcript_id}, summary_id={summary['id']}"
        )
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        log(f"E2E smoke failed: {error}")
        raise
