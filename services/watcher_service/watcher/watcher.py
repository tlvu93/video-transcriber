import hashlib
import logging
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Optional

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watcher.config import (
    API_TIMEOUT_SECONDS,
    API_URL,
    FILE_STABILITY_CHECK_INTERVAL_SECONDS,
    FILE_STABILITY_MAX_WAIT_SECONDS,
    FILE_STABILITY_REQUIRED_CHECKS,
    VIDEO_DIRS,
)

from common.messaging import RabbitMQClient, publish_video_created_event

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watcher")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()


def calculate_file_hash(file_path):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def wait_for_file_stability(file_path: str) -> bool:
    """Wait until a file stops changing size before registering it."""
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


def process_video_file(file_path):
    """Process a video file and add it to the database via API."""
    try:
        storage_path = os.path.abspath(file_path)
        # Get the filename from the path
        filename = os.path.basename(storage_path)
        logger.info(f"Processing video file: {filename}")

        # Calculate file hash
        file_hash = calculate_file_hash(storage_path)
        logger.info(f"File hash: {file_hash}")

        # Check if the video already exists in the database via API
        check_url = f"{API_URL}/videos/check"
        check_data = {"filename": filename, "file_hash": file_hash}

        try:
            response = requests.post(check_url, json=check_data, timeout=API_TIMEOUT_SECONDS)
            response.raise_for_status()

            existing_video = response.json()
            if existing_video:
                logger.info(f"Video {filename} already exists in the database with ID: {existing_video['id']}")
                return
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking if video exists: {str(e)}")
            # Continue with registration even if check fails

        # Register the video via API
        register_url = f"{API_URL}/videos/register"
        register_data = {
            "filename": filename,
            "file_hash": file_hash,
            "storage_path": storage_path,
            "video_metadata": {"file_hash": file_hash},
        }

        try:
            response = requests.post(register_url, json=register_data, timeout=API_TIMEOUT_SECONDS)
            response.raise_for_status()

            video = response.json()
            logger.info(f"Added video {filename} to the database with ID: {video['id']}")

            # Create a transcription job for the video via API
            job_url = f"{API_URL}/transcription-jobs/"
            job_data = {"video_id": video["id"]}

            job_response = requests.post(job_url, json=job_data, timeout=API_TIMEOUT_SECONDS)
            job_response.raise_for_status()

            job = job_response.json()
            logger.info(f"Created transcription job {job['id']} for video {video['id']} via API")

            # Publish video created event
            try:
                rabbitmq_client.connect()
                publish_video_created_event(rabbitmq_client, str(video["id"]), filename)
                logger.info(f"Published video.created event for video {video['id']}")
            except Exception as e:
                logger.error(f"Error publishing event: {str(e)}")
                logger.info("Continuing with processing as transcription job was already created via API")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error registering video or creating job: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Error processing video file {file_path}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


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
        except Exception as e:
            logger.error(f"❌ Error in processing after file event: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
        finally:
            with self._lock:
                self._scheduled_paths.discard(file_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info(f"🔍 Detected new video file: {event.src_path}")
            self.schedule_video(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info(f"🔄 Detected modified video file: {event.src_path}")
            self.schedule_video(event.src_path)


def ensure_directories():
    """Create all necessary directories for the application."""
    try:
        logger.info("Creating necessary directories...")
        for video_dir in VIDEO_DIRS:
            os.makedirs(video_dir, exist_ok=True)
            logger.info(f"Video directory: {video_dir}")

        logger.info("All directories created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating directories: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise


def process_existing_files():
    """Process existing video files in all video directories and their subdirectories."""
    for video_dir in VIDEO_DIRS:
        logger.info(f"Processing existing video files in {video_dir} (including subdirectories)")

        try:
            for root, _, files in os.walk(video_dir):
                for filename in files:
                    if filename.endswith((".mp4", ".mov", ".mkv")):
                        file_path = os.path.join(root, filename)
                        logger.info(f"Found existing video file: {file_path}")
                        if wait_for_file_stability(file_path):
                            process_video_file(file_path)
        except Exception as e:
            logger.error(f"❌ Error processing existing files in {video_dir}: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")


def check_api_connection():
    """Check if the API service is available."""
    logger.info(f"Checking connection to API service at {API_URL}")

    try:
        response = requests.get(f"{API_URL}/", timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        logger.info("API service is available")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error connecting to API service: {str(e)}")
        return False


def check_rabbitmq_connection():
    """Check if the RabbitMQ service is available."""
    logger.info("Checking connection to RabbitMQ service")

    try:
        rabbitmq_client.connect()
        logger.info("RabbitMQ service is available")
        rabbitmq_client.close()
        return True
    except Exception as e:
        logger.error(f"❌ Error connecting to RabbitMQ service: {str(e)}")
        return False


def start_watching():
    logger.info("Starting video transcriber watcher")

    try:
        # Ensure all required directories exist
        ensure_directories()

        # Check API connection
        if not check_api_connection():
            logger.error("Cannot connect to API service. Exiting.")
            return

        # Check RabbitMQ connection
        check_rabbitmq_connection()
        # Continue even if RabbitMQ is not available, we'll fall back to API

        # Process existing files
        process_existing_files()

        event_handler = VideoFolderHandler()
        observer = Observer()

        # Schedule observers for all video directories
        for video_dir in VIDEO_DIRS:
            observer.schedule(event_handler, video_dir, recursive=True)
            logger.info(f"Starting file observer for {video_dir}")

        observer.start()

        logger.info("👀 Watching for changes in video directories...")
        logger.info("📋 Press Ctrl+C to stop")

        try:
            # Keep the script running
            logger.info("Entering watch loop")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping observer")
            observer.stop()
        observer.join()
        logger.info("File observer stopped")
    except Exception as e:
        logger.error(f"❌ Error in watcher: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    try:
        logger.info("Starting video transcriber watcher module")
        start_watching()
        logger.info("Watcher module execution completed")
    except Exception as e:
        logger.error(f"❌ Fatal error in watcher module: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
