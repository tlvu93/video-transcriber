import time
import sys
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import VIDEO_DIR, TRANSCRIPT_DIR, DB_PATH
from main import main

class VideoFolderHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            print(f"🔍 Detected new video file: {event.src_path}")
            main()
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith((".mp4", ".mov", ".mkv")):
            print(f"🔄 Detected modified video file: {event.src_path}")
            main()

def ensure_directories():
    """Create all necessary directories for the application."""
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def start_watching():
    # Ensure all required directories exist
    ensure_directories()
    
    event_handler = VideoFolderHandler()
    observer = Observer()
    observer.schedule(event_handler, VIDEO_DIR, recursive=False)
    observer.start()
    
    print(f"👀 Watching for changes in {VIDEO_DIR}...")
    print(f"📋 Press Ctrl+C to stop")
    
    try:
        # Run main once at startup to process any existing files
        print("🚀 Running initial processing...")
        main()
        
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watching()
