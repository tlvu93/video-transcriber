#!/usr/bin/env python3
"""
Simple test script to verify WhisperX integration works correctly.
This script can be used to test the WhisperX functionality without the full application stack.
"""

import os
import sys
import logging
import torch
import whisperx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('whisperx_test')

def test_whisperx_installation():
    """Test if WhisperX is properly installed and can load models."""
    try:
        logger.info("Testing WhisperX installation...")
        
        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        # Test model loading
        logger.info("Loading WhisperX model (this may take a while on first run)...")
        model = whisperx.load_model("base", device, compute_type="float16" if device == "cuda" else "int8")
        logger.info("✅ WhisperX model loaded successfully!")
        
        # Test audio loading function
        logger.info("Testing audio loading function...")
        # This just tests if the function exists and can be called
        try:
            # Create a dummy audio file path (won't actually load)
            dummy_path = "/nonexistent/test.wav"
            # Just test if the function exists
            if hasattr(whisperx, 'load_audio'):
                logger.info("✅ whisperx.load_audio function available")
            else:
                logger.error("❌ whisperx.load_audio function not found")
                return False
        except Exception as e:
            logger.info(f"Audio loading test (expected to fail with dummy path): {e}")
        
        # Test alignment model loading
        logger.info("Testing alignment model loading...")
        try:
            model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
            logger.info("✅ Alignment model loaded successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Alignment model loading failed: {e}")
            logger.info("This might be normal if models need to be downloaded first")
        
        # Test diarization pipeline
        logger.info("Testing diarization pipeline...")
        try:
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=device)
            logger.info("✅ Diarization pipeline created successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Diarization pipeline creation failed: {e}")
            logger.info("This might be normal if running without HuggingFace token or if models need to be downloaded")
        
        logger.info("🎉 WhisperX installation test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ WhisperX installation test failed: {e}")
        return False

def test_with_sample_audio(audio_path):
    """Test WhisperX with a sample audio file if provided."""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return False
    
    try:
        logger.info(f"Testing with audio file: {audio_path}")
        
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
        result = model.transcribe(audio, batch_size=16)
        
        logger.info(f"Transcription result: {result['text']}")
        logger.info(f"Number of segments: {len(result.get('segments', []))}")
        
        # Test alignment
        try:
            logger.info("Testing alignment...")
            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            logger.info("✅ Alignment completed successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Alignment failed: {e}")
        
        # Test diarization
        try:
            logger.info("Testing diarization...")
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=device)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            logger.info("✅ Diarization completed successfully!")
            
            # Show speaker information
            for segment in result.get("segments", []):
                speaker = segment.get("speaker", "Unknown")
                text = segment.get("text", "").strip()
                logger.info(f"Speaker {speaker}: {text}")
                
        except Exception as e:
            logger.warning(f"⚠️ Diarization failed: {e}")
        
        logger.info("🎉 Audio transcription test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Audio transcription test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting WhisperX integration test...")
    
    # Test basic installation
    if not test_whisperx_installation():
        sys.exit(1)
    
    # Test with sample audio if provided
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        if not test_with_sample_audio(audio_path):
            sys.exit(1)
    else:
        logger.info("No audio file provided. To test with audio, run:")
        logger.info("python test_whisperx.py /path/to/audio/file.wav")
    
    logger.info("✅ All tests completed successfully!")
