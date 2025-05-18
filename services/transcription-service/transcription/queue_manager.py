import logging
import threading
import time
import queue
from typing import Dict, Any, List, Optional, Callable
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('queue_manager')

class TranscriptionQueueManager:
    """
    Queue manager for transcription jobs.
    Manages a queue of transcription jobs and processes them using worker threads.
    """
    
    def __init__(self, max_workers: int = 1):
        """
        Initialize the queue manager.
        
        Args:
            max_workers: Maximum number of worker threads to use
        """
        self.max_workers = max_workers
        self.job_queue = queue.Queue()
        self.active_jobs = {}  # job_id -> job_data
        self.workers = []
        self.running = False
        self.lock = threading.Lock()
        self.job_processor = None
        
        logger.info(f"Initialized queue manager with {max_workers} workers")
    
    def start(self, job_processor: Callable[[str], bool]):
        """
        Start the queue manager.
        
        Args:
            job_processor: Function to process a job, takes job_id and returns success status
        """
        if self.running:
            logger.warning("Queue manager is already running")
            return
        
        self.job_processor = job_processor
        self.running = True
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"transcription-worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker thread {i}")
        
        logger.info("Queue manager started")
    
    def stop(self):
        """
        Stop the queue manager.
        """
        if not self.running:
            logger.warning("Queue manager is not running")
            return
        
        self.running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=5)
        
        self.workers = []
        logger.info("Queue manager stopped")
    
    def add_job(self, job_data: Dict[str, Any]):
        """
        Add a job to the queue.
        
        Args:
            job_data: Job data including job_id
        """
        job_id = job_data.get("id")
        if not job_id:
            logger.error("Cannot add job without id")
            return
        
        with self.lock:
            # Check if job is already in queue or being processed
            if job_id in self.active_jobs:
                logger.warning(f"Job {job_id} is already in the queue or being processed")
                return
            
            # Add job to queue
            self.job_queue.put(job_data)
            self.active_jobs[job_id] = job_data
            logger.info(f"Added job {job_id} to queue, queue size: {self.job_queue.qsize()}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the status of the queue.
        
        Returns:
            Dictionary with queue status information
        """
        with self.lock:
            return {
                "queue_size": self.job_queue.qsize(),
                "active_jobs": len(self.active_jobs),
                "max_workers": self.max_workers,
                "running": self.running
            }
    
    def _worker_thread(self):
        """
        Worker thread function.
        Processes jobs from the queue.
        """
        while self.running:
            try:
                # Get job from queue
                try:
                    job_data = self.job_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                job_id = job_data.get("id")
                if not job_id:
                    logger.error("Job data does not contain id")
                    self.job_queue.task_done()
                    continue
                
                logger.info(f"Processing job {job_id}")
                
                # Process job
                try:
                    success = self.job_processor(job_id)
                    if success:
                        logger.info(f"Job {job_id} processed successfully")
                    else:
                        logger.error(f"Job {job_id} processing failed")
                        # Job failed but was handled by the processor
                        # No need to retry as the processor has already marked it as failed
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {str(e)}")
                    logger.error(f"Exception traceback: {traceback.format_exc()}")
                    # Unhandled exception in the processor
                    # The job might need to be retried or manually fixed
                
                # Remove job from active jobs
                with self.lock:
                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]
                
                # Mark job as done
                self.job_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in worker thread: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
                time.sleep(1)  # Avoid tight loop in case of error
