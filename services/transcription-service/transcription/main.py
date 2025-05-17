import argparse
import logging
import time
import requests
import traceback
from typing import Optional

from transcription.config import API_URL
from transcription.transcription_worker import process_transcription_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription')

def get_next_transcription_job_api():
    """Get the next pending transcription job from the API."""
    try:
        response = requests.get(f"{API_URL}/transcription-jobs/next")
        if response.status_code == 404:
            # No pending jobs
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting next transcription job: {str(e)}")
        return None

def run_worker(poll_interval: int = 5):
    """
    Run the transcription worker.
    
    Args:
        poll_interval: Interval in seconds between polling for new jobs
    """
    logger.info(f"Starting transcription worker with poll interval of {poll_interval} seconds")
    
    # Main worker loop
    while True:
        try:
            # Get the next job from API
            job = get_next_transcription_job_api()
            
            if job:
                logger.info(f"Processing transcription job {job['id']} for video {job['video_id']}")
                
                try:
                    # Process the job
                    success = process_transcription_job(job['id'])
                    
                    if success:
                        logger.info(f"Transcription job {job['id']} completed successfully")
                    else:
                        logger.error(f"Transcription job {job['id']} failed")
                
                except Exception as e:
                    logger.exception(f"Error processing transcription job {job['id']}: {str(e)}")
            
            else:
                # No jobs to process, wait for poll_interval seconds
                logger.debug(f"No transcription jobs to process, waiting {poll_interval} seconds")
            
            # Sleep for poll_interval seconds
            time.sleep(poll_interval)
            
        except Exception as e:
            logger.exception(f"Error in worker loop: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            time.sleep(poll_interval)  # Sleep and try again

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcription worker")
    parser.add_argument("--poll-interval", type=int, default=5, help="Interval in seconds between polling for new jobs")
    args = parser.parse_args()
    
    # Run the worker
    run_worker(args.poll_interval)
