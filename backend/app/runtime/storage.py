import os
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

from backend.app.runtime.config import DATA_DIR, VIDEO_DIR, VIDEO_DIRS


StorageReservationCheck = Callable[[str], bool]


@dataclass(frozen=True)
class StorageWriteTarget:
    local_path: str
    storage_uri: str


@dataclass
class LocalFilesystemStorageBackend:
    primary_video_dir: str = VIDEO_DIR
    video_dirs: tuple[str, ...] = tuple(VIDEO_DIRS)
    backend_name: str = "local_fs"

    def normalize_uri(self, uri: Optional[str]) -> Optional[str]:
        if not uri:
            return None
        return os.path.abspath(uri)

    def resolve_video_path(
        self,
        filename: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> str:
        candidate_paths = []
        if storage_uri:
            candidate_paths.append(self.normalize_uri(storage_uri))

        candidate_paths.append(os.path.join(self.primary_video_dir, filename))
        for video_dir in self.video_dirs:
            candidate_paths.append(os.path.join(video_dir, filename))

        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)

        raise FileNotFoundError(f"Video file not found: {filename}")

    def prepare_upload_target(
        self,
        filename: str,
        *,
        is_reserved: StorageReservationCheck,
    ) -> StorageWriteTarget:
        safe_filename = os.path.basename(filename)
        stem, suffix = os.path.splitext(safe_filename)
        counter = 0

        while True:
            candidate_name = safe_filename if counter == 0 else f"{stem}_{counter}{suffix}"
            candidate_path = os.path.abspath(os.path.join(self.primary_video_dir, candidate_name))
            if not os.path.exists(candidate_path) and not is_reserved(candidate_path):
                return StorageWriteTarget(
                    local_path=candidate_path,
                    storage_uri=candidate_path,
                )
            counter += 1

    def iter_watch_roots(self) -> tuple[str, ...]:
        return tuple(
            os.path.abspath(video_dir)
            for video_dir in self.video_dirs
        )

    def supports_file_watch(self) -> bool:
        return bool(self.iter_watch_roots())


@dataclass
class S3CompatibleStorageBackend:
    bucket: str = os.environ.get("S3_STORAGE_BUCKET", "video-transcriber").strip() or "video-transcriber"
    prefix: str = os.environ.get("S3_STORAGE_PREFIX", "uploads").strip().strip("/")
    mount_root: str = os.path.abspath(
        os.environ.get("S3_STORAGE_MOUNT_ROOT", os.path.join(DATA_DIR, "object-storage"))
    )
    backend_name: str = "s3_compatible"

    def _build_uri(self, bucket: str, key: str) -> str:
        normalized_key = key.strip("/")
        return f"s3://{bucket}/{normalized_key}" if normalized_key else f"s3://{bucket}"

    def _mounted_path_for_uri(self, storage_uri: str) -> str:
        parsed = urlparse(storage_uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"Unsupported S3-compatible storage URI: {storage_uri}")

        bucket = parsed.netloc
        key = unquote(parsed.path.lstrip("/"))
        path_parts = [self.mount_root, bucket]
        if key:
            path_parts.extend(part for part in key.split("/") if part)
        return os.path.abspath(os.path.join(*path_parts))

    def _storage_uri_from_mounted_path(self, mounted_path: str) -> Optional[str]:
        normalized_path = os.path.abspath(mounted_path)
        mount_root = os.path.abspath(self.mount_root)

        if normalized_path == mount_root or not normalized_path.startswith(f"{mount_root}{os.sep}"):
            return None

        relative_path = os.path.relpath(normalized_path, mount_root)
        parts = [part for part in relative_path.split(os.sep) if part]
        if not parts:
            return None

        bucket = parts[0]
        key = "/".join(parts[1:])
        return self._build_uri(bucket, key)

    def _candidate_key(self, filename: str) -> str:
        safe_filename = os.path.basename(filename)
        if self.prefix:
            return f"{self.prefix}/{safe_filename}"
        return safe_filename

    def normalize_uri(self, uri: Optional[str]) -> Optional[str]:
        if not uri:
            return None

        if uri.startswith("s3://"):
            parsed = urlparse(uri)
            if not parsed.netloc:
                raise ValueError(f"Invalid S3-compatible storage URI: {uri}")
            return self._build_uri(parsed.netloc, unquote(parsed.path.lstrip("/")))

        mounted_uri = self._storage_uri_from_mounted_path(uri)
        if mounted_uri:
            return mounted_uri

        if os.path.isabs(uri):
            return os.path.abspath(uri)

        return self._build_uri(self.bucket, self._candidate_key(uri))

    def resolve_video_path(
        self,
        filename: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> str:
        candidate_paths = []
        if storage_uri:
            normalized_uri = self.normalize_uri(storage_uri)
            if normalized_uri and normalized_uri.startswith("s3://"):
                candidate_paths.append(self._mounted_path_for_uri(normalized_uri))
            elif normalized_uri:
                candidate_paths.append(os.path.abspath(normalized_uri))
        else:
            candidate_paths.append(
                self._mounted_path_for_uri(
                    self._build_uri(self.bucket, self._candidate_key(filename))
                )
            )

        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)

        raise FileNotFoundError(f"Video file not found: {filename}")

    def prepare_upload_target(
        self,
        filename: str,
        *,
        is_reserved: StorageReservationCheck,
    ) -> StorageWriteTarget:
        safe_filename = os.path.basename(filename)
        stem, suffix = os.path.splitext(safe_filename)
        counter = 0

        while True:
            candidate_name = safe_filename if counter == 0 else f"{stem}_{counter}{suffix}"
            candidate_uri = self._build_uri(self.bucket, self._candidate_key(candidate_name))
            candidate_path = self._mounted_path_for_uri(candidate_uri)
            if not os.path.exists(candidate_path) and not is_reserved(candidate_uri):
                return StorageWriteTarget(
                    local_path=candidate_path,
                    storage_uri=candidate_uri,
                )
            counter += 1

    def iter_watch_roots(self) -> tuple[str, ...]:
        bucket_root = os.path.join(self.mount_root, self.bucket)
        return (os.path.abspath(bucket_root),)

    def supports_file_watch(self) -> bool:
        return bool(self.bucket and self.mount_root)


def get_storage_backend():
    backend_name = os.environ.get("STORAGE_BACKEND", "local_fs").strip().lower()
    if backend_name == "s3_compatible":
        return S3CompatibleStorageBackend()
    return LocalFilesystemStorageBackend()
