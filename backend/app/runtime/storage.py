import os
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from backend.app.runtime.config import DATA_DIR, VIDEO_DIR, VIDEO_DIRS

StorageReservationCheck = Callable[[str], bool]


def _is_within_directory(path: str, directory: str) -> bool:
    """Return True if the resolved `path` is inside `directory` (no traversal/symlink escape)."""
    try:
        real_path = os.path.realpath(path)
        real_directory = os.path.realpath(directory)
    except OSError:
        return False

    return real_path == real_directory or real_path.startswith(real_directory + os.sep)


def _first_contained_existing_path(candidates: list[str], allowed_roots: tuple[str, ...]) -> str | None:
    """Return the first candidate that is an existing regular file contained within an allowed root."""
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        resolved = os.path.abspath(candidate)
        if any(_is_within_directory(resolved, root) for root in allowed_roots):
            return resolved
    return None


@dataclass(frozen=True)
class StorageWriteTarget:
    local_path: str
    storage_uri: str


@dataclass
class LocalFilesystemStorageBackend:
    primary_video_dir: str = VIDEO_DIR
    video_dirs: tuple[str, ...] = tuple(VIDEO_DIRS)
    backend_name: str = "local_fs"

    def normalize_uri(self, uri: str | None) -> str | None:
        if not uri:
            return None
        return os.path.abspath(uri)

    def resolve_video_path(
        self,
        filename: str,
        *,
        storage_uri: str | None = None,
    ) -> str:
        allowed_roots = (os.path.abspath(self.primary_video_dir), *(os.path.abspath(d) for d in self.video_dirs))

        candidate_paths = []
        if storage_uri:
            normalized = self.normalize_uri(storage_uri)
            if normalized:
                candidate_paths.append(normalized)

        # Only ever consider the basename of the caller-supplied filename: this backend never
        # serves nested paths by filename alone, so stripping directory components here closes
        # off "../" traversal and absolute-path overrides (os.path.join discards prior segments
        # when a later one is absolute) before we ever touch the filesystem.
        safe_filename = os.path.basename(filename) if filename else ""
        if safe_filename:
            candidate_paths.append(os.path.join(self.primary_video_dir, safe_filename))
            for video_dir in self.video_dirs:
                candidate_paths.append(os.path.join(video_dir, safe_filename))

        resolved = _first_contained_existing_path(candidate_paths, allowed_roots)
        if resolved is None:
            raise FileNotFoundError(f"Video file not found: {filename}")
        return resolved

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
        # Reject "." / ".." path segments so a crafted key (e.g. "../../etc/passwd") can never
        # walk the resolved path outside of `mount_root`.
        key_parts = [part for part in key.split("/") if part not in ("", ".", "..")]
        if key and len(key_parts) != len([part for part in key.split("/") if part]):
            raise ValueError(f"Invalid S3-compatible storage key: {storage_uri}")

        path_parts = [self.mount_root, bucket, *key_parts]
        resolved = os.path.abspath(os.path.join(*path_parts))
        if not _is_within_directory(resolved, self.mount_root):
            raise ValueError(f"Storage URI resolves outside of the storage mount root: {storage_uri}")
        return resolved

    def _storage_uri_from_mounted_path(self, mounted_path: str) -> str | None:
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

    def normalize_uri(self, uri: str | None) -> str | None:
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
            # An absolute path that isn't already under `mount_root` is untrusted input (it can
            # arrive straight from an API request body): never pass it through as-is. Re-key it
            # by basename under the configured bucket/prefix instead of trusting the raw path.
            return self._build_uri(self.bucket, self._candidate_key(os.path.basename(uri)))

        return self._build_uri(self.bucket, self._candidate_key(uri))

    def resolve_video_path(
        self,
        filename: str,
        *,
        storage_uri: str | None = None,
    ) -> str:
        allowed_roots = (os.path.abspath(self.mount_root),)
        candidate_paths = []
        try:
            if storage_uri:
                normalized_uri = self.normalize_uri(storage_uri)
                if normalized_uri and normalized_uri.startswith("s3://"):
                    candidate_paths.append(self._mounted_path_for_uri(normalized_uri))
            else:
                candidate_paths.append(
                    self._mounted_path_for_uri(
                        self._build_uri(self.bucket, self._candidate_key(filename))
                    )
                )
        except ValueError as error:
            raise FileNotFoundError(f"Video file not found: {filename}") from error

        resolved = _first_contained_existing_path(candidate_paths, allowed_roots)
        if resolved is None:
            raise FileNotFoundError(f"Video file not found: {filename}")
        return resolved

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
