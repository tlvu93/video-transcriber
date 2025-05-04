import whisper
import os
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import TRANSCRIPT_DIR, VIDEO_DIR
from utils import get_video_metadata
from summarizer import create_summary

model = whisper.load_model("base")

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

def process_video(filepath):
    try:
        # Check if file exists and is accessible
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return None, None, None
            
        # Get video metadata
        try:
            metadata = get_video_metadata(filepath)
        except Exception as e:
            print(f"⚠️ Error getting metadata: {str(e)}")
            metadata = {"error": str(e)}
        
        print(f"🔊 Transcribing: {os.path.basename(filepath)}")
        
        # Transcribe video
        try:
            result = model.transcribe(filepath, verbose=False)
            transcript_text = result["text"]
        except Exception as e:
            print(f"❌ Transcription error: {str(e)}")
            return None, metadata, None
        
        basename = os.path.splitext(os.path.basename(filepath))[0]
        
        # Save transcript
        transcript_path = os.path.join(TRANSCRIPT_DIR, f"{basename}.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        print(f"📝 Transcript saved to: {transcript_path}")

        # Save .srt if segments are available
        if "segments" in result:
            srt_path = os.path.join(TRANSCRIPT_DIR, f"{basename}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result["segments"]):
                    f.write(f"{i+1}\n")
                    f.write(f"{format_srt_timestamp(seg['start'])} --> {format_srt_timestamp(seg['end'])}\n")
                    f.write(f"{seg['text'].strip()}\n\n")
            print(f"📝 SRT file saved to: {srt_path}")
        
        # Generate summary from transcript
        try:
            summary = create_summary(transcript_text, filepath)
        except Exception as e:
            print(f"⚠️ Summary generation error: {str(e)}")
            summary = f"Error generating summary: {str(e)}"

        return transcript_text, metadata, summary
        
    except Exception as e:
        print(f"❌ Error processing video: {str(e)}")
        return None, None, None

def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
