import os
import sys
import logging
import threading
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, migrate_from_json_to_db
from src.transcription_worker import start_worker as start_transcription_worker
from src.summarization_worker import start_worker as start_summarization_worker
from src.api import app as api_app
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main')

def start_workers():
    """Start worker processes in separate threads."""
    # Start transcription worker
    logger.info("Starting transcription worker thread...")
    transcription_thread = threading.Thread(target=start_transcription_worker)
    transcription_thread.daemon = True
    transcription_thread.start()
    
    # Start summarization worker
    logger.info("Starting summarization worker thread...")
    summarization_thread = threading.Thread(target=start_summarization_worker)
    summarization_thread.daemon = True
    summarization_thread.start()
    
    logger.info("Worker threads started")

def main():
    """Main entry point."""
    try:
        logger.info("Starting Video Transcriber API")
        
        # Create necessary directories
        os.makedirs("data/videos", exist_ok=True)
        os.makedirs("data/transcriptions", exist_ok=True)
        os.makedirs("data/summaries", exist_ok=True)
        
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        
        # Migrate data from JSON to database
        logger.info("Migrating data from JSON to database...")
        migrate_from_json_to_db()
        
        # Start worker processes
        start_workers()
        
        # Start API server
        logger.info("Starting API server...")
        uvicorn.run(api_app, host="0.0.0.0", port=8000)
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        raise

if __name__ == "__main__":
    main()
