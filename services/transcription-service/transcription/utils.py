import os
import json
import logging
import subprocess
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('utils')

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
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            filepath
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
        video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        if video_streams:
            video_stream = video_streams[0]
            video_info.update({
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "codec": video_stream.get("codec_name", "unknown"),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),
            })
        
        # Extract audio stream info
        audio_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
        if audio_streams:
            audio_stream = audio_streams[0]
            video_info.update({
                "audio_codec": audio_stream.get("codec_name", "unknown"),
                "audio_channels": audio_stream.get("channels", 0),
                "audio_sample_rate": audio_stream.get("sample_rate", 0),
            })
        
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
