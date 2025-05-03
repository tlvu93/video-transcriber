import whisper
import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import TRANSCRIPT_DIR, VIDEO_DIR
from utils import get_video_metadata

model = whisper.load_model("base")

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

def process_video(filepath):
    metadata = get_video_metadata(filepath)
    print(f"Extracting from: {filepath}")
    
    result = model.transcribe(filepath, verbose=False)
    
    basename = os.path.splitext(os.path.basename(filepath))[0]
    
    # Save transcript
    with open(os.path.join(TRANSCRIPT_DIR, f"{basename}.txt"), "w") as f:
        f.write(result["text"])

    # Save .srt if segments are available
    if "segments" in result:
        with open(os.path.join(TRANSCRIPT_DIR, f"{basename}.srt"), "w") as f:
            for i, seg in enumerate(result["segments"]):
                f.write(f"{i+1}\n")
                f.write(f"{format_srt_timestamp(seg['start'])} --> {format_srt_timestamp(seg['end'])}\n")
                f.write(f"{seg['text'].strip()}\n\n")

    return result["text"], metadata

def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
