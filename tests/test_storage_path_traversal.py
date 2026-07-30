"""Regression tests for path-traversal protection in the storage backends.

These cover the vulnerability where a client-supplied `filename` or
`storage_path` (e.g. via `POST /videos/register`) could be joined directly
onto a trusted directory and used to read/serve arbitrary files on disk
(CWE-22 / CWE-73).
"""

from __future__ import annotations

import os

import pytest

from backend.app.runtime.storage import (
    LocalFilesystemStorageBackend,
    S3CompatibleStorageBackend,
)


@pytest.fixture
def local_backend(tmp_path):
    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    secret_dir = tmp_path / "outside"
    secret_dir.mkdir()
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text("top secret")

    legit_file = video_dir / "clip.mp4"
    legit_file.write_bytes(b"fake video bytes")

    backend = LocalFilesystemStorageBackend(
        primary_video_dir=str(video_dir),
        video_dirs=(str(video_dir),),
    )
    return backend, video_dir, secret_file, legit_file


def test_resolve_video_path_returns_legit_file(local_backend):
    backend, _video_dir, _secret_file, legit_file = local_backend
    resolved = backend.resolve_video_path("clip.mp4")
    assert resolved == os.path.abspath(str(legit_file))


def test_resolve_video_path_rejects_relative_traversal_in_filename(local_backend):
    backend, video_dir, secret_file, _legit_file = local_backend
    relative = os.path.relpath(str(secret_file), str(video_dir))
    with pytest.raises(FileNotFoundError):
        backend.resolve_video_path(relative)


def test_resolve_video_path_rejects_absolute_filename(local_backend):
    backend, _video_dir, secret_file, _legit_file = local_backend
    with pytest.raises(FileNotFoundError):
        backend.resolve_video_path(str(secret_file))


def test_resolve_video_path_rejects_traversal_via_storage_uri(local_backend):
    backend, _video_dir, secret_file, _legit_file = local_backend
    # No same-named file exists under the video dir, so there is no legitimate fallback:
    # a malicious `storage_uri` pointing outside the allowed roots must be rejected outright.
    with pytest.raises(FileNotFoundError):
        backend.resolve_video_path("does-not-exist-in-video-dir.mp4", storage_uri=str(secret_file))


def test_resolve_video_path_ignores_malicious_storage_uri_and_falls_back_safely(local_backend):
    backend, _video_dir, secret_file, legit_file = local_backend
    # Even when a same-named legitimate file exists, a malicious `storage_uri` must never be
    # the one returned - the function should fall back to the safe, contained candidate.
    resolved = backend.resolve_video_path("clip.mp4", storage_uri=str(secret_file))
    assert resolved == os.path.abspath(str(legit_file))
    assert resolved != os.path.abspath(str(secret_file))


def test_resolve_video_path_rejects_dotdot_only_filename(local_backend):
    backend, _video_dir, _secret_file, _legit_file = local_backend
    with pytest.raises(FileNotFoundError):
        backend.resolve_video_path("..")


@pytest.fixture
def s3_backend(tmp_path):
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    backend = S3CompatibleStorageBackend(
        bucket="videos",
        prefix="uploads",
        mount_root=str(mount_root),
    )
    bucket_dir = mount_root / "videos" / "uploads"
    bucket_dir.mkdir(parents=True)
    legit_file = bucket_dir / "clip.mp4"
    legit_file.write_bytes(b"fake video bytes")

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("top secret")

    return backend, mount_root, secret_file, legit_file


def test_s3_resolve_video_path_returns_legit_file(s3_backend):
    backend, _mount_root, _secret_file, legit_file = s3_backend
    resolved = backend.resolve_video_path("clip.mp4")
    assert resolved == os.path.abspath(str(legit_file))


def test_s3_mounted_path_rejects_dotdot_key_segments(s3_backend):
    backend, _mount_root, _secret_file, _legit_file = s3_backend
    with pytest.raises(ValueError):
        backend._mounted_path_for_uri("s3://videos/../../../etc/passwd")


def test_s3_resolve_video_path_rejects_traversal_storage_uri(s3_backend):
    backend, _mount_root, _secret_file, _legit_file = s3_backend
    with pytest.raises(FileNotFoundError):
        backend.resolve_video_path("clip.mp4", storage_uri="s3://videos/../../../../etc/passwd")


def test_s3_normalize_uri_does_not_leak_arbitrary_absolute_path(s3_backend):
    backend, _mount_root, secret_file, _legit_file = s3_backend
    normalized = backend.normalize_uri(str(secret_file))
    # An arbitrary absolute path outside of mount_root must be re-keyed by basename
    # under the configured bucket, never passed through verbatim.
    assert normalized == f"s3://videos/uploads/{os.path.basename(str(secret_file))}"
