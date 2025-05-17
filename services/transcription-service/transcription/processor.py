import whisper
import os
import sys
import logging
import traceback
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from transcription.config import VIDEO_DIR
from transcription.utils import get_video_metadata
from summarization_service.summarization.summarizer import create_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('processor')

logger.info("Loading Whisper model...")
model = whisper.load_model("base")
logger.info("Whisper model loaded successfully")

os.makedirs(VIDEO_DIR, exist_ok=True)

logger.info(f"Video directory: {VIDEO_DIR}")


def process_video(filepath):
    logger.info(f"Processing video: {filepath}")
    try:
        # Check if file exists and is accessible
        if not os.path.exists(filepath):
            logger.error(f"❌ File not found: {filepath}")
            return None, None, None
            
        # Get video metadata
        try:
            logger.info(f"Getting metadata for: {os.path.basename(filepath)}")
            metadata = get_video_metadata(filepath)
            logger.info(f"Metadata retrieved successfully")
        except Exception as e:
            logger.error(f"⚠️ Error getting metadata: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            metadata = {"error": str(e)}
        
        logger.info(f"🔊 Transcribing: {os.path.basename(filepath)}")
        
        # Transcribe video
        try:
            logger.info("Starting Whisper transcription...")
            result = model.transcribe(filepath, verbose=False)
            transcript_text = result["text"]
            logger.info(f"Transcription completed, length: {len(transcript_text)} characters")
        except Exception as e:
            logger.error(f"❌ Transcription error: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return None, metadata, None
        
  
        
        # Generate summary from transcript
        logger.info("Starting summary generation...")
        try:
            summary = create_summary(transcript_text, filepath)
            logger.info(f"Summary generated successfully, length: {len(summary)} characters")
        except Exception as e:
            logger.error(f"⚠️ Summary generation error: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            summary = f"Error generating summary: {str(e)}"

        return transcript_text, metadata, summary
        
    except Exception as e:
        logger.error(f"❌ Error processing video: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None, None, None

def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
