import os
import sys
import logging
import traceback
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import VIDEO_DIR
from database import load_db, save_db
from utils import get_file_hash
from processor import process_video

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main')

def main():
    logger.info("Starting main processing function")
    logger.info(f"Looking for video files in: {VIDEO_DIR}")
    
    try:
        db = load_db()
        logger.info(f"Database loaded, contains {len(db)} processed files")
        
        files = [f for f in os.listdir(VIDEO_DIR) if f.endswith((".mp4", ".mov", ".mkv"))]
        logger.info(f"Found {len(files)} video files")
        
        for fname in files:
            logger.info(f"Processing file: {fname}")
            path = os.path.join(VIDEO_DIR, fname)
            
            try:
                file_hash = get_file_hash(path)
                
                # Skip files that couldn't be accessed
                if file_hash is None:
                    logger.warning(f"⚠️  Skipping inaccessible file: {fname}")
                    continue
                    
                # Skip files that have already been processed
                if file_hash in db:
                    logger.info(f"⚠️  Skipping duplicate: {fname}")
                    continue
                
                try:
                    logger.info(f"📥 New file found: {fname}")
                    transcript, metadata, summary = process_video(path)
                    
                    if transcript is None:
                        logger.error(f"Failed to generate transcript for {fname}")
                        continue
                        
                    logger.info(f"Updating database for {fname}")
                    db[file_hash] = {
                        "filename": fname,
                        "transcript_preview": transcript[:100] if transcript else "",
                        "summary_preview": summary[:100] if summary else "No summary available",
                        "metadata": metadata
                    }
                    
                    # Check if summary was generated
                    if summary:
                        logger.info(f"Summary generated for {fname}: {summary[:100]}...")
                    else:
                        logger.warning(f"No summary was generated for {fname}")
                    
                    save_db(db)
                    logger.info(f"✅ Done: {fname}")
                except Exception as e:
                    logger.error(f"❌ Error processing {fname}: {str(e)}")
                    logger.error(f"Exception traceback: {traceback.format_exc()}")
            except Exception as e:
                logger.error(f"❌ Error with file hash for {fname}: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
    except Exception as e:
        logger.error(f"❌ Main process error: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    logger.info("Starting video transcriber main module")
    main()
    logger.info("Main module execution completed")
