import sys
import logging
import argparse

from .database import init_db
from .transcription_worker import start_worker as start_transcription_worker
from .summarization_worker import start_worker as start_summarization_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('worker')

def main():
    """Main entry point for worker processes."""
    parser = argparse.ArgumentParser(description='Start a worker process')
    parser.add_argument('worker_type', choices=['transcription', 'summarization'], 
                        help='Type of worker to start')
    parser.add_argument('--poll-interval', type=int, default=5,
                        help='Time in seconds to wait between polling for new jobs')
    
    args = parser.parse_args()
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Start worker based on type
    if args.worker_type == 'transcription':
        logger.info("Starting transcription worker...")
        start_transcription_worker(args.poll_interval)
    elif args.worker_type == 'summarization':
        logger.info("Starting summarization worker...")
        start_summarization_worker(args.poll_interval)
    else:
        logger.error(f"Unknown worker type: {args.worker_type}")
        sys.exit(1)

if __name__ == "__main__":
    main()
