import hashlib
import logging
import os
import threading
import time
import traceback
from typing import Optional

from sqlalchemy import text
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backend.app.persistence.database import engine
from backend.app.domain.records import register_watched_video
from backend.app.runtime.storage import get_storage_backend
from backend.app.watcher.config import (
    FILE_STABILITY_CHECK_INTERVAL_SECONDS,
    FILE_STABILITY_MAX_WAIT_SECONDS,
    FILE_STABILITY_REQUIRED_CHECKS,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watcher")
storage_backend = get_storage_backend()


def calculate_file_hash(file_path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def wait_for_file_stability(file_path: str) -> bool:
    stable_checks = 0
    last_size: Optional[int] = None
    deadline = time.time() + FILE_STABILITY_MAX_WAIT_SECONDS

    while time.time() < deadline:
        try:
            current_size = os.path.getsize(file_path)
        except OSError:
            logger.info("File disappeared while waiting for stability: %s", file_path)
            return False

        if current_size == last_size and current_size > 0:
            stable_checks += 1
            if stable_checks >= FILE_STABILITY_REQUIRED_CHECKS:
                return True
        else:
            stable_checks = 0
            last_size = current_size

        time.sleep(FILE_STABILITY_CHECK_INTERVAL_SECONDS)

    logger.warning("Timed out waiting for file stability: %s", file_path)
    return False


def process_video_file(file_path: str) -> None:
    try:
        storage_path = storage_backend.normalize_uri(file_path) or os.path.abspath(file_path)
        filename = os.path.basename(storage_path)
        logger.info("Processing video file: %s", filename)

        local_path = os.path.abspath(file_path)
        file_hash = calculate_file_hash(local_path)
        logger.info("File hash: %s", file_hash)

        result = register_watched_video(
            filename=filename,
            file_hash=file_hash,
            storage_path=storage_path,
            video_metadata={"file_hash": file_hash},
        )
        video = result["video"]
        job = result.get("job")

        if result.get("created"):
            logger.info("Added video %s to the database with ID: %s", filename, video["id"])
            if job:
                logger.info("Created transcription job %s for video %s", job["id"], video["id"])
            return

        logger.info(
            "Video %s already exists in the database with ID: %s (match=%s)",
            filename,
            video["id"],
            result.get("match_reason") or "unknown",
        )
    except Exception as error:
        logger.error("Error processing video file %s: %s", file_path, error)
        logger.error("Exception traceback: %s", traceback.format_exc())


class VideoFolderHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._scheduled_paths: set[str] = set()
        self._lock = threading.Lock()

    def schedule_video(self, file_path: str) -> None:
        normalized_path = os.path.abspath(file_path)

        with self._lock:
            if normalized_path in self._scheduled_paths:
                logger.debug("File is already queued for watcher processing: %s", normalized_path)
                return
            self._scheduled_paths.add(normalized_path)

        thread = threading.Thread(
            target=self._process_when_stable,
            args=(normalized_path,),
            daemon=True,
            name=f"watcher-stability-{os.path.basename(normalized_path)}",
        )
        thread.start()

    def _process_when_stable(self, file_path: str) -> None:
        try:
            if wait_for_file_stability(file_path):
                process_video_file(file_path)
        except Exception as error:
            logger.error("Error in processing after file event: %s", error)
            logger.error("Exception traceback: %s", traceback.format_exc())
        finally:
            with self._lock:
                self._scheduled_paths.discard(file_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info("Detected new video file: %s", event.src_path)
            self.schedule_video(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info("Detected modified video file: %s", event.src_path)
            self.schedule_video(event.src_path)


def ensure_directories() -> None:
    try:
        logger.info("Creating necessary directories...")
        for video_dir in storage_backend.iter_watch_roots():
            os.makedirs(video_dir, exist_ok=True)
            logger.info("Video directory: %s", video_dir)
        logger.info("All directories created successfully")
    except Exception as error:
        logger.error("Error creating directories: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
        raise


def process_existing_files() -> None:
    for video_dir in storage_backend.iter_watch_roots():
        logger.info("Processing existing video files in %s (including subdirectories)", video_dir)

        try:
            for root, _, files in os.walk(video_dir):
                for filename in files:
                    if filename.endswith((".mp4", ".mov", ".mkv")):
                        file_path = os.path.join(root, filename)
                        logger.info("Found existing video file: %s", file_path)
                        if wait_for_file_stability(file_path):
                            process_video_file(file_path)
        except Exception as error:
            logger.error("Error processing existing files in %s: %s", video_dir, error)
            logger.error("Exception traceback: %s", traceback.format_exc())


def check_backend_connection() -> bool:
    logger.info("Checking database connection for watcher")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Backend database is available")
        return True
    except Exception as error:
        logger.error("Error connecting to backend database: %s", error)
        return False


def start_watching() -> None:
    logger.info("Starting video transcriber watcher")

    try:
        if not storage_backend.supports_file_watch():
            logger.info(
                "Storage backend %s does not expose watchable roots. Watcher will stay idle.",
                getattr(storage_backend, "backend_name", "unknown"),
            )
            return

        watch_roots = storage_backend.iter_watch_roots()
        if not watch_roots:
            logger.info("No watch roots configured for the current storage backend")
            return

        ensure_directories()

        if not check_backend_connection():
            logger.error("Cannot connect to backend database. Exiting.")
            return

        process_existing_files()

        event_handler = VideoFolderHandler()
        observer = Observer()

        for video_dir in watch_roots:
            observer.schedule(event_handler, video_dir, recursive=True)
            logger.info("Starting file observer for %s", video_dir)

        observer.start()

        logger.info("Watching for changes in video directories...")
        logger.info("Press Ctrl+C to stop")

        try:
            logger.info("Entering watch loop")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping observer")
            observer.stop()
        observer.join()
        logger.info("File observer stopped")
    except Exception as error:
        logger.error("Error in watcher: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())


if __name__ == "__main__":
    try:
        logger.info("Starting video transcriber watcher module")
        start_watching()
        logger.info("Watcher module execution completed")
    except Exception as error:
        logger.error("Fatal error in watcher module: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
