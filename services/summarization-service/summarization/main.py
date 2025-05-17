import argparse
import logging
import time
import requests
import traceback
from typing import Optional

from summarization.config import API_URL
from summarization.worker import process_summarization_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization')

def get_next_summarization_job_api():
    """Get the next pending summarization job from the API."""
    try:
        response = requests.get(f"{API_URL}/summarization-jobs/next")
        if response.status_code == 404:
            # No pending jobs
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting next summarization job: {str(e)}")
        return None

def mark_job_started_api(job_id: str) -> None:
    """Mark job as started via API."""
    response = requests.post(f"{API_URL}/summarization-jobs/{job_id}/start")
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as started")

def mark_job_completed_api(job_id: str, processing_time: float) -> None:
    """Mark job as completed via API."""
    data = {"processing_time_seconds": processing_time}
    response = requests.post(f"{API_URL}/summarization-jobs/{job_id}/complete", json=data)
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as completed in {processing_time:.2f} seconds")

def mark_job_failed_api(job_id: str, error_details: dict) -> None:
    """Mark job as failed via API."""
    response = requests.post(f"{API_URL}/summarization-jobs/{job_id}/fail", json={"error_details": error_details})
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as failed: {error_details}")

def run_worker(poll_interval: int = 5):
    """
    Run the summarization worker.
    
    Args:
        poll_interval: Interval in seconds between polling for new jobs
    """
    logger.info(f"Starting summarization worker with poll interval of {poll_interval} seconds")
    
    # Main worker loop
    while True:
        try:
            # Get the next job from API
            job = get_next_summarization_job_api()
            
            if job:
                logger.info(f"Processing summarization job {job['id']} for transcript {job['transcript_id']}")
                
                try:
                    # Mark job as started
                    mark_job_started_api(job['id'])
                    
                    # Process the job
                    start_time = time.time()
                    success, error_details = process_summarization_job(job['id'])
                    processing_time = time.time() - start_time
                    
                    # Mark job as completed or failed
                    if success:
                        mark_job_completed_api(job['id'], processing_time)
                        logger.info(f"Summarization job {job['id']} completed in {processing_time:.2f} seconds")
                    else:
                        mark_job_failed_api(job['id'], error_details)
                        logger.error(f"Summarization job {job['id']} failed: {error_details}")
                
                except Exception as e:
                    # Mark job as failed
                    error_details = {"error": str(e), "type": type(e).__name__}
                    mark_job_failed_api(job['id'], error_details)
                    logger.exception(f"Error processing summarization job {job['id']}: {str(e)}")
            
            else:
                # No jobs to process, wait for poll_interval seconds
                logger.debug(f"No summarization jobs to process, waiting {poll_interval} seconds")
            
            # Sleep for poll_interval seconds
            time.sleep(poll_interval)
            
        except Exception as e:
            logger.exception(f"Error in worker loop: {str(e)}")
            time.sleep(poll_interval)  # Sleep and try again

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Summarization worker")
    parser.add_argument("--poll-interval", type=int, default=5, help="Interval in seconds between polling for new jobs")
    args = parser.parse_args()
    
    # Run the worker
    run_worker(args.poll_interval)
