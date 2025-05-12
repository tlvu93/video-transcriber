import os
import logging
import time
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from common.models import SummarizationJob, Transcript, Summary, Video
from common.config import TRANSCRIPT_DIR, SUMMARY_DIR

from summarization.summarizer import generate_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization.worker')

def process_summarization_job(job: SummarizationJob, db: Session) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Process a summarization job.
    
    Args:
        job: The summarization job to process
        db: Database session
        
    Returns:
        Tuple of (success, error_details)
    """
    try:
        # Get the transcript
        transcript = db.query(Transcript).filter(Transcript.id == job.transcript_id).first()
        if not transcript:
            return False, {"error": f"Transcript not found: {job.transcript_id}"}
        
        # Get the transcript content
        transcript_content = transcript.content
        
        # Create summary file path
        if transcript.video_id:
            # Get the video filename
            video = db.query(Video).filter(Video.id == transcript.video_id).first()
            if video:
                summary_filename = f"{os.path.splitext(video.filename)[0]}_summary.txt"
            else:
                summary_filename = f"transcript_{transcript.id}_summary.txt"
        else:
            summary_filename = f"transcript_{transcript.id}_summary.txt"
        
        summary_path = os.path.join(SUMMARY_DIR, summary_filename)
        
        # Ensure summary directory exists
        os.makedirs(SUMMARY_DIR, exist_ok=True)
        
        # Generate summary
        logger.info(f"Generating summary for transcript: {transcript.id}")
        summary_text = generate_summary(transcript_content)
        
        # Save summary to file
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        
        # Create summary record
        summary = Summary(
            transcript_id=transcript.id,
            content=summary_text,
            status="completed"
        )
        db.add(summary)
        db.commit()
        
        # Update transcript status
        transcript.status = "summarized"
        db.commit()
        
        return True, None
        
    except Exception as e:
        logger.exception(f"Error processing summarization job: {str(e)}")
        return False, {"error": str(e), "type": type(e).__name__}
