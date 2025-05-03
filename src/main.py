import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import VIDEO_DIR
from database import load_db, save_db
from utils import get_file_hash
from processor import process_video

def main():
    db = load_db()
    files = [f for f in os.listdir(VIDEO_DIR) if f.endswith((".mp4", ".mov", ".mkv"))]
    
    for fname in files:
        path = os.path.join(VIDEO_DIR, fname)
        file_hash = get_file_hash(path)
        
        if file_hash in db:
            print(f"⚠️  Skipping duplicate: {fname}")
            continue
        
        print(f"📥 New file found: {fname}")
        transcript, metadata = process_video(path)
        
        db[file_hash] = {
            "filename": fname,
            "transcript_preview": transcript[:100],
            "metadata": metadata
        }
        save_db(db)
        print(f"✅ Done: {fname}")

if __name__ == "__main__":
    main()
