"""Unit tests for the SSRF guard on the yt-dlp URL download endpoint.

`POST /videos/youtube` hands a client-supplied URL straight to yt-dlp, which
will fetch it server-side. Without validation this is a textbook SSRF vector
(e.g. targeting the cloud metadata endpoint or internal services). These
tests cover `validate_download_url`'s scheme and address-range checks.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://videotranscriber:videotranscriber@localhost:5432/videotranscriber",
)

from fastapi import HTTPException  # noqa: E402

from backend.app.api.app import validate_download_url  # noqa: E402


def test_allows_public_https_url():
    validate_download_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # should not raise


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "not-a-url",
    ],
)
def test_rejects_disallowed_scheme(url):
    with pytest.raises(HTTPException) as exc_info:
        validate_download_url(url)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
    ],
)
def test_rejects_local_and_private_targets(url):
    with pytest.raises(HTTPException) as exc_info:
        validate_download_url(url)
    assert exc_info.value.status_code == 400
