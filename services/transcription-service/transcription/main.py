import argparse
import logging
import time
import requests
import traceback
import json
import os
import sys
from typing import Dict, Any, Optional

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from transcription.config import API_URL
from transcription.transcription_worker import process_transcription_job
from transcription.queue_manager import TranscriptionQueueManager
from common.messaging import (
    RabbitMQClient, 
    EVENT_VIDEO_CREATED,
    EVENT_JOB_STATUS_CHANGED,
    publish_job_status_changed_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription')

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

# Initialize queue manager (will be set in main)
queue_manager = None

def get_next_transcription_job_api() -> Optional[Dict[str, Any]]:
    """
    Get the next pending transcription job from the API.
    
    Returns:
        The next pending transcription job, or None if no jobs are pending
    """
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

def handle_video_created_event(event_data: Dict[str, Any]):
    """
    Handle a video.created event.
    
    Args:
        event_data: The event data
    """
    try:
        video_id = event_data.get("video_id")
        filename = event_data.get("filename")
        
        if not video_id:
            logger.error("Received video.created event without video_id")
            return
        
        logger.info(f"Received video.created event for video {video_id} ({filename})")
        
        # Get the next transcription job from the API
        # The API service should have already created a transcription job for this video
        job = get_next_transcription_job_api()
        
        if job and job["video_id"] == video_id:
            logger.info(f"Adding transcription job {job['id']} for video {video_id} to queue")
            queue_manager.add_job(job)
        else:
            logger.warning(f"No transcription job found for video {video_id}")
    
    except Exception as e:
        logger.error(f"Error handling video.created event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

def handle_job_status_changed_event(event_data: Dict[str, Any]):
    """
    Handle a job.status.changed event.
    
    Args:
        event_data: The event data
    """
    try:
        job_type = event_data.get("job_type")
        job_id = event_data.get("job_id")
        status = event_data.get("status")
        
        if not job_type or not job_id or not status:
            logger.error("Received job.status.changed event with missing data")
            return
        
        # Only process transcription jobs
        if job_type != "transcription":
            return
        
        logger.info(f"Received job.status.changed event for {job_type} job {job_id}: {status}")
        
        # If the job is pending, add it to the queue
        if status == "pending":
            # Get job details
            try:
                response = requests.get(f"{API_URL}/transcription-jobs/{job_id}")
                response.raise_for_status()
                job = response.json()
                
                logger.info(f"Adding transcription job {job_id} to queue")
                queue_manager.add_job(job)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error getting job details: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error handling job.status.changed event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

def run_event_based_worker(max_workers: int = 1, poll_interval: int = 5):
    """
    Run the transcription worker in event-based mode.
    
    Args:
        max_workers: Maximum number of worker threads to use
        poll_interval: Interval in seconds between polling for new jobs
    """
    global queue_manager
    
    logger.info(f"Starting transcription worker in event-based mode with {max_workers} workers")
    
    try:
        # Initialize queue manager
        queue_manager = TranscriptionQueueManager(max_workers=max_workers, poll_interval=poll_interval)
        queue_manager.start(process_transcription_job, get_next_transcription_job_api)
        
        # Connect to RabbitMQ
        rabbitmq_client.connect()
        
        # Subscribe to video.created events
        rabbitmq_client.subscribe_to_event(
            EVENT_VIDEO_CREATED,
            handle_video_created_event,
            "transcription_video_created_queue"
        )
        
        # Subscribe to job.status.changed events
        rabbitmq_client.subscribe_to_event(
            EVENT_JOB_STATUS_CHANGED,
            handle_job_status_changed_event,
            "transcription_job_status_queue"
        )
        
        # Process any existing pending jobs
        logger.info("Checking for existing pending jobs")
        job = get_next_transcription_job_api()
        if job:
            logger.info(f"Found pending transcription job {job['id']} for video {job['video_id']}")
            queue_manager.add_job(job)
        
        # Start consuming messages
        logger.info("Waiting for events...")
        rabbitmq_client.start_consuming()
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        queue_manager.stop()
        rabbitmq_client.stop_consuming()
        rabbitmq_client.close()
    
    except Exception as e:
        logger.error(f"Error in event-based worker: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        if queue_manager:
            queue_manager.stop()
        rabbitmq_client.close()

def run_polling_worker(max_workers: int = 1, poll_interval: int = 5):
    """
    Run the transcription worker in polling mode.
    
    Args:
        max_workers: Maximum number of worker threads to use
        poll_interval: Interval in seconds between polling for new jobs
    """
    global queue_manager
    
    logger.info(f"Starting transcription worker in polling mode with {max_workers} workers and {poll_interval}s poll interval")
    
    try:
        # Initialize queue manager
        queue_manager = TranscriptionQueueManager(max_workers=max_workers, poll_interval=poll_interval)
        queue_manager.start(process_transcription_job, get_next_transcription_job_api)
        
        # Keep main thread alive
        while True:
            try:
                # Log queue status periodically
                status = queue_manager.get_queue_status()
                logger.info(f"Queue status: {status}")
                time.sleep(60)  # Log status every minute
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down")
                queue_manager.stop()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
                time.sleep(poll_interval)
    
    except Exception as e:
        logger.exception(f"Error in polling worker: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        if queue_manager:
            queue_manager.stop()

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcription worker")
    parser.add_argument("--poll-interval", type=int, default=5, help="Interval in seconds between polling for new jobs")
    parser.add_argument("--mode", type=str, choices=["event", "poll"], default="event", help="Worker mode: event-based or polling")
    parser.add_argument("--max-workers", type=int, default=1, help="Maximum number of worker threads to use")
    args = parser.parse_args()
    
    # Run the worker in the specified mode
    if args.mode == "event":
        run_event_based_worker(args.max_workers, args.poll_interval)
    else:
        run_polling_worker(args.max_workers, args.poll_interval)
