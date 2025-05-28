#!/usr/bin/env python3
"""
Quick test script to verify the transcription service setup without heavy dependencies.
This script tests basic functionality that doesn't require WhisperX or PyTorch.
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('quick_test')

def test_basic_imports():
    """Test basic imports that don't require heavy ML dependencies."""
    logger.info("Testing basic imports...")
    
    try:
        # Test project imports
        from transcription.config import VIDEO_DIR, VIDEO_DIRS, API_URL
        logger.info("✅ Configuration imported successfully")
        logger.info(f"Video directories: {VIDEO_DIRS}")
        logger.info(f"API URL: {API_URL}")
        
        from transcription.processor import find_video_file, format_srt_timestamp
        logger.info("✅ Processor functions imported successfully")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during imports: {e}")
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

def test_directory_structure():
    """Test that required directories exist or can be created."""
    logger.info("Testing directory structure...")
    
    try:
        from transcription.config import VIDEO_DIRS
        
        for video_dir in VIDEO_DIRS:
            if not os.path.exists(video_dir):
                os.makedirs(video_dir, exist_ok=True)
                logger.info(f"✅ Created directory: {video_dir}")
            else:
                logger.info(f"✅ Directory exists: {video_dir}")
        
        # Test test directories
        test_dirs = ["test_audio", "test_results"]
        for test_dir in test_dirs:
            if not os.path.exists(test_dir):
                os.makedirs(test_dir, exist_ok=True)
                logger.info(f"✅ Created test directory: {test_dir}")
            else:
                logger.info(f"✅ Test directory exists: {test_dir}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Directory structure test failed: {e}")
        return False

def check_optional_dependencies():
    """Check which optional dependencies are available."""
    logger.info("Checking optional dependencies...")
    
    dependencies = {
        "torch": "PyTorch (required for WhisperX)",
        "whisperx": "WhisperX (main transcription engine)",
        "numpy": "NumPy (numerical operations)",
        "soundfile": "SoundFile (audio I/O)",
        "librosa": "Librosa (audio processing)",
    }
    
    available = []
    missing = []
    
    for dep, description in dependencies.items():
        try:
            __import__(dep)
            available.append(f"✅ {dep} - {description}")
        except ImportError:
            missing.append(f"❌ {dep} - {description}")
    
    logger.info("Available dependencies:")
    for dep in available:
        logger.info(f"  {dep}")
    
    if missing:
        logger.info("Missing dependencies (install with setup script):")
        for dep in missing:
            logger.info(f"  {dep}")
    
    return len(available), len(missing)

def main():
    """Run quick tests."""
    logger.info("🚀 Starting quick transcription service tests...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Basic imports
    total_tests += 1
    if test_basic_imports():
        tests_passed += 1
    
    # Test 2: Utility functions
    total_tests += 1
    if test_utility_functions():
        tests_passed += 1
    
    # Test 3: Video file discovery
    total_tests += 1
    if test_video_file_discovery():
        tests_passed += 1
    
    # Test 4: Directory structure
    total_tests += 1
    if test_directory_structure():
        tests_passed += 1
    
    # Check optional dependencies
    available_deps, missing_deps = check_optional_dependencies()
    
    # Summary
    logger.info(f"\n🎯 Test Results: {tests_passed}/{total_tests} basic tests passed")
    logger.info(f"📦 Dependencies: {available_deps} available, {missing_deps} missing")
    
    if tests_passed == total_tests:
        logger.info("🎉 Basic tests passed! Core functionality is working.")
        if missing_deps > 0:
            logger.info("💡 To run full transcription tests, install missing dependencies:")
            logger.info("   ./setup_standalone.sh")
        else:
            logger.info("🚀 All dependencies available! You can run full tests:")
            logger.info("   python standalone_test.py")
        return True
    else:
        logger.error(f"❌ {total_tests - tests_passed} basic test(s) failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
