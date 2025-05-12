import time
import sys
import os
import logging
import traceback
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.common.config import VIDEO_DIR, TRANSCRIPT_DIR, SUMMARY_DIR, DB_PATH
from api_service.api.main import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('watcher')

class VideoFolderHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info(f"🔍 Detected new video file: {event.src_path}")
            try:
                main()
            except Exception as e:
                logger.error(f"❌ Error in main processing after file creation: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            logger.info(f"🔄 Detected modified video file: {event.src_path}")
            try:
                main()
            except Exception as e:
                logger.error(f"❌ Error in main processing after file modification: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")

def ensure_directories():
    """Create all necessary directories for the application."""
    try:
        logger.info("Creating necessary directories...")
        os.makedirs(VIDEO_DIR, exist_ok=True)
        logger.info(f"Video directory: {VIDEO_DIR}")
        
        os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
        logger.info(f"Transcript directory: {TRANSCRIPT_DIR}")
        
        os.makedirs(SUMMARY_DIR, exist_ok=True)
        logger.info(f"Summary directory: {SUMMARY_DIR}")
        
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        logger.info(f"Database directory: {os.path.dirname(DB_PATH)}")
        
        logger.info("All directories created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating directories: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise

def start_watching():
    logger.info("Starting video transcriber watcher")
    
    try:
        # Ensure all required directories exist
        ensure_directories()
        
        event_handler = VideoFolderHandler()
        observer = Observer()
        observer.schedule(event_handler, VIDEO_DIR, recursive=False)
        
        logger.info(f"Starting file observer for {VIDEO_DIR}")
        observer.start()
        
        logger.info(f"👀 Watching for changes in {VIDEO_DIR}...")
        logger.info(f"📋 Press Ctrl+C to stop")
        
        try:
            # Run main once at startup to process any existing files
            logger.info("🚀 Running initial processing...")
            main()
            
            # Keep the script running
            logger.info("Entering watch loop")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping observer")
            observer.stop()
        observer.join()
        logger.info("File observer stopped")
    except Exception as e:
        logger.error(f"❌ Error in watcher: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        logger.info("Starting video transcriber watcher module")
        start_watching()
        logger.info("Watcher module execution completed")
    except Exception as e:
        logger.error(f"❌ Fatal error in watcher module: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
