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
        
        # Skip files that couldn't be accessed
        if file_hash is None:
            print(f"⚠️  Skipping inaccessible file: {fname}")
            continue
            
        # Skip files that have already been processed
        if file_hash in db:
            print(f"⚠️  Skipping duplicate: {fname}")
            continue
        
        try:
            print(f"📥 New file found: {fname}")
            transcript, metadata, summary = process_video(path)
            
            db[file_hash] = {
                "filename": fname,
                "transcript_preview": transcript[:100] if transcript else "",
                "summary_preview": summary[:100] if summary else "No summary available",
                "metadata": metadata
            }
            save_db(db)
            print(f"✅ Done: {fname}")
        except Exception as e:
            print(f"❌ Error processing {fname}: {str(e)}")

if __name__ == "__main__":
    main()
