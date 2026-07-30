"""Unit tests for upload validation helpers in backend.app.api.app.

Covers the file-type allowlist and streaming size cap added to the
`POST /videos/` upload endpoint (previously: no extension check, no size
limit, and the raw client-supplied filename was persisted verbatim).
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi import HTTPException, UploadFile

from backend.app.api.app import validate_upload_filename, write_upload_with_size_limit


def test_validate_upload_filename_accepts_allowed_extension():
    assert validate_upload_filename("meeting.mp4") == "meeting.mp4"


def test_validate_upload_filename_rejects_disallowed_extension():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename("payload.exe")
    assert exc_info.value.status_code == 415


def test_validate_upload_filename_rejects_empty_filename():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename("")
    assert exc_info.value.status_code == 400


def test_validate_upload_filename_rejects_no_extension():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename("noextension")
    assert exc_info.value.status_code == 415


def _make_upload_file(data: bytes) -> UploadFile:
    return UploadFile(filename="clip.mp4", file=io.BytesIO(data))


def test_write_upload_with_size_limit_writes_full_file(tmp_path):
    destination = tmp_path / "clip.mp4"
    payload = b"x" * 1024
    upload = _make_upload_file(payload)

    written = write_upload_with_size_limit(upload, str(destination), max_bytes=10 * 1024)

    assert written == len(payload)
    assert destination.read_bytes() == payload


def test_write_upload_with_size_limit_rejects_oversized_upload_and_cleans_up(tmp_path):
    destination = tmp_path / "clip.mp4"
    payload = b"x" * 2048
    upload = _make_upload_file(payload)

    with pytest.raises(HTTPException) as exc_info:
        write_upload_with_size_limit(upload, str(destination), max_bytes=1024)

    assert exc_info.value.status_code == 413
    # The partially-written file must not be left behind on disk.
    assert not os.path.exists(destination)
