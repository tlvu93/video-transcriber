import argparse
import logging
import time
from typing import Optional

from common.database import init_db, get_db
from common.job_queue import get_next_summarization_job, mark_job_started, mark_job_completed, mark_job_failed

from summarization.worker import process_summarization_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization')

def run_worker(poll_interval: int = 5):
    """
    Run the summarization worker.
    
    Args:
        poll_interval: Interval in seconds between polling for new jobs
    """
    logger.info(f"Starting summarization worker with poll interval of {poll_interval} seconds")
    
    # Initialize database
    init_db()
    
    # Main worker loop
    while True:
        try:
            # Get a database session
            with get_db() as db:
                # Get the next job
                job = get_next_summarization_job(db)
                
                if job:
                    logger.info(f"Processing summarization job {job.id} for transcript {job.transcript_id}")
                    
                    try:
                        # Mark job as started
                        mark_job_started(job, db)
                        
                        # Process the job
                        start_time = time.time()
                        success, error_details = process_summarization_job(job, db)
                        processing_time = time.time() - start_time
                        
                        # Mark job as completed or failed
                        if success:
                            mark_job_completed(job, processing_time, db)
                            logger.info(f"Summarization job {job.id} completed in {processing_time:.2f} seconds")
                        else:
                            mark_job_failed(job, error_details, db)
                            logger.error(f"Summarization job {job.id} failed: {error_details}")
                    
                    except Exception as e:
                        # Mark job as failed
                        error_details = {"error": str(e), "type": type(e).__name__}
                        mark_job_failed(job, error_details, db)
                        logger.exception(f"Error processing summarization job {job.id}: {str(e)}")
                
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
