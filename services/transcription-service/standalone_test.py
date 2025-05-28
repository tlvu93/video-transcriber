#!/usr/bin/env python3
"""
Standalone test script for the transcription service.
This script can test the transcription functionality without requiring other services.
"""

import os
import sys
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('standalone_test')

def test_imports():
    """Test if all required modules can be imported."""
    logger.info("Testing imports...")
    
    try:
        # Test basic imports
        import torch
        logger.info(f"✅ PyTorch imported successfully (version: {torch.__version__})")
        
        import whisperx
        logger.info("✅ WhisperX imported successfully")
        
        # Test project imports
        from transcription.processor import find_video_file, format_srt_timestamp
        from transcription.utils import get_video_metadata
        from transcription.config import VIDEO_DIR, VIDEO_DIRS, API_URL
        
        logger.info("✅ All transcription modules imported successfully")
        logger.info(f"Video directories: {VIDEO_DIRS}")
        logger.info(f"API URL: {API_URL}")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during imports: {e}")
        return False

def test_whisperx_basic():
    """Test basic WhisperX functionality."""
    logger.info("Testing WhisperX basic functionality...")
    
    try:
        import torch
        import whisperx
        
        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        # Test model loading
        logger.info("Loading WhisperX model (this may take a while on first run)...")
        model = whisperx.load_model("base", device, compute_type="float16" if device == "cuda" else "int8")
        logger.info("✅ WhisperX model loaded successfully!")
        
        # Test if audio loading function exists
        if hasattr(whisperx, 'load_audio'):
            logger.info("✅ whisperx.load_audio function available")
        else:
            logger.error("❌ whisperx.load_audio function not found")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ WhisperX test failed: {e}")
        return False

def test_video_file_discovery():
    """Test video file discovery functionality."""
    logger.info("Testing video file discovery...")
    
    try:
        from transcription.processor import find_video_file
        from transcription.config import VIDEO_DIRS
        
        # Create test directories if they don't exist
        for video_dir in VIDEO_DIRS:
            os.makedirs(video_dir, exist_ok=True)
            logger.info(f"Video directory: {video_dir}")
        
        # Test with non-existent file
        result = find_video_file("/nonexistent/test.mp4")
        if result is None:
            logger.info("✅ Correctly handled non-existent file")
        else:
            logger.warning(f"Unexpected result for non-existent file: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Video file discovery test failed: {e}")
        return False

def test_utility_functions():
    """Test utility functions."""
    logger.info("Testing utility functions...")
    
    try:
        from transcription.processor import format_srt_timestamp
        
        # Test timestamp formatting
        test_cases = [
            (0, "00:00:00,000"),
            (61.5, "00:01:01,500"),
            (3661.123, "01:01:01,123"),
        ]
        
        for seconds, expected in test_cases:
            result = format_srt_timestamp(seconds)
            if result == expected:
                logger.info(f"✅ Timestamp formatting: {seconds}s -> {result}")
            else:
                logger.error(f"❌ Timestamp formatting failed: {seconds}s -> {result} (expected {expected})")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Utility functions test failed: {e}")
        return False

def test_transcription_with_sample_audio(audio_path: str):
    """Test transcription with a sample audio file."""
    logger.info(f"Testing transcription with audio file: {audio_path}")
    
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return False
    
    try:
        import torch
        import whisperx
        
        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model
        logger.info("Loading WhisperX model...")
        model = whisperx.load_model("base", device, compute_type="float16" if device == "cuda" else "int8")
        
        # Load audio
        logger.info("Loading audio...")
        audio = whisperx.load_audio(audio_path)
        
        # Transcribe
        logger.info("Transcribing...")
        start_time = time.time()
        result = model.transcribe(audio, batch_size=16)
        processing_time = time.time() - start_time
        
        logger.info(f"Transcription completed in {processing_time:.2f} seconds")
        logger.info(f"Detected language: {result.get('language', 'unknown')}")
        logger.info(f"Transcription result: {result['text']}")
        logger.info(f"Number of segments: {len(result.get('segments', []))}")
        
        # Show segments
        for i, segment in enumerate(result.get('segments', [])[:5]):  # Show first 5 segments
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            text = segment.get('text', '').strip()
            logger.info(f"Segment {i+1}: [{start:.2f}s - {end:.2f}s] {text}")
        
        # Test alignment if possible
        try:
            logger.info("Testing alignment...")
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
            aligned_result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            logger.info("✅ Alignment completed successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Alignment failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Audio transcription test failed: {e}")
        return False

def create_sample_audio_file():
    """Create a simple sample audio file for testing."""
    logger.info("Creating sample audio file for testing...")
    
    try:
        import numpy as np
        import soundfile as sf
        
        # Create a simple sine wave audio file
        sample_rate = 16000
        duration = 5  # 5 seconds
        frequency = 440  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
        
        # Add some variation to make it more interesting
        audio_data += np.sin(2 * np.pi * frequency * 2 * t) * 0.1
        
        sample_path = "test_sample.wav"
        sf.write(sample_path, audio_data, sample_rate)
        
        logger.info(f"✅ Created sample audio file: {sample_path}")
        return sample_path
        
    except ImportError:
        logger.warning("⚠️ soundfile not available, cannot create sample audio")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create sample audio: {e}")
        return None

def main():
    """Run all standalone tests."""
    logger.info("🚀 Starting standalone transcription service tests...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Imports
    total_tests += 1
    if test_imports():
        tests_passed += 1
    
    # Test 2: WhisperX basic functionality
    total_tests += 1
    if test_whisperx_basic():
        tests_passed += 1
    
    # Test 3: Video file discovery
    total_tests += 1
    if test_video_file_discovery():
        tests_passed += 1
    
    # Test 4: Utility functions
    total_tests += 1
    if test_utility_functions():
        tests_passed += 1
    
    # Test 5: Audio transcription (if audio file provided)
    audio_file = None
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        # Try to create a sample audio file
        audio_file = create_sample_audio_file()
    
    if audio_file:
        total_tests += 1
        if test_transcription_with_sample_audio(audio_file):
            tests_passed += 1
        
        # Clean up sample file if we created it
        if audio_file == "test_sample.wav" and os.path.exists(audio_file):
            os.remove(audio_file)
            logger.info("Cleaned up sample audio file")
    else:
        logger.info("No audio file provided or created. Skipping transcription test.")
        logger.info("To test with audio, run: python standalone_test.py /path/to/audio/file.wav")
    
    # Summary
    logger.info(f"\n🎯 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        logger.info("🎉 All tests passed! Transcription service is ready for standalone use.")
        return True
    else:
        logger.error(f"❌ {total_tests - tests_passed} test(s) failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
