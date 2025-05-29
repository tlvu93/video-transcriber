import os
import json
import logging
import subprocess
from typing import Dict, Any

from transcription.config import VIDEO_DIRS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("utils")


def get_video_metadata(filepath: str) -> Dict[str, Any]:
    """
    Get metadata for a video file using ffprobe.

    Args:
        filepath: Path to the video file

    Returns:
        Dictionary containing video metadata
    """
    logger.info(f"Getting metadata for video: {filepath}")

    try:
        # Run ffprobe to get video metadata
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            filepath,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)

        # Extract relevant metadata
        video_info = {
            "filename": os.path.basename(filepath),
            "format": metadata.get("format", {}).get("format_name", "unknown"),
            "duration": float(metadata.get("format", {}).get("duration", 0)),
            "size": int(metadata.get("format", {}).get("size", 0)),
            "bitrate": int(metadata.get("format", {}).get("bit_rate", 0)),
        }

        # Extract video stream info
        video_streams = [
            s for s in metadata.get("streams", []) if s.get("codec_type") == "video"
        ]
        if video_streams:
            video_stream = video_streams[0]
            video_info.update(
                {
                    "width": video_stream.get("width", 0),
                    "height": video_stream.get("height", 0),
                    "codec": video_stream.get("codec_name", "unknown"),
                    "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                }
            )

        # Extract audio stream info
        audio_streams = [
            s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"
        ]
        if audio_streams:
            audio_stream = audio_streams[0]
            video_info.update(
                {
                    "audio_codec": audio_stream.get("codec_name", "unknown"),
                    "audio_channels": audio_stream.get("channels", 0),
                    "audio_sample_rate": audio_stream.get("sample_rate", 0),
                }
            )

        logger.info(f"Video metadata retrieved successfully: {video_info}")
        return video_info

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running ffprobe: {e}")
        logger.error(f"ffprobe stderr: {e.stderr}")
        return {"error": f"Error running ffprobe: {e}"}

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing ffprobe output: {e}")
        return {"error": f"Error parsing ffprobe output: {e}"}

    except Exception as e:
        logger.error(f"Error getting video metadata: {e}")
        return {"error": f"Error getting video metadata: {e}"}


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds as HH:MM:SS.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes as human-readable string.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted file size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def find_video_file(filepath):
    """Find video file in configured directories."""
    logger.info(f"Processing video: {filepath}")

    # Check if file exists and is accessible
    if os.path.exists(filepath):
        return filepath

    # If file doesn't exist at the expected path, try to find it in all video directories and their subdirectories
    filename = os.path.basename(filepath)
    logger.info(
        f"File not found at {filepath}, searching in all video directories for {filename}..."
    )

    # Search in all configured video directories
    for video_dir in VIDEO_DIRS:
        # First check directly in the video directory
        test_path = os.path.join(video_dir, filename)
        if os.path.exists(test_path):
            logger.info(f"Found video file at: {test_path}")
            return test_path

        # Then search in subdirectories
        for root, _, files in os.walk(video_dir):
            if filename in files:
                found_path = os.path.join(root, filename)
                logger.info(f"Found video file at: {found_path}")
                return found_path

    logger.error(f"❌ File not found: {filename}")
    return None


def format_srt_timestamp(seconds):
    """Format seconds as SRT timestamp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
