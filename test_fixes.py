#!/usr/bin/env python3
"""
Test script to verify the fixes for Ollama API and language detection issues.
"""

import logging
import sys
from pathlib import Path

# Add the services to the path
sys.path.insert(0, str(Path(__file__).parent / "services" / "translation_service"))
sys.path.insert(0, str(Path(__file__).parent / "services" / "transcription_service"))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_fixes")

def test_language_normalization():
    """Test the language normalization function."""
    logger.info("Testing language normalization...")
    
    try:
        from transcription.transcription_worker import normalize_language_code
        
        # Test cases
        test_cases = [
            ("en", "en"),
            ("eng", "en"),
            ("de", "de"),
            ("ger", "de"),
            ("deu", "de"),
            ("fr", "fr"),
            ("fra", "fr"),
            ("fre", "fr"),
            ("es", "es"),
            ("spa", "es"),
            ("ja", "ja"),
            ("jpn", "ja"),
            ("unknown", "en"),  # Should default to en
            ("", "en"),  # Should default to en
            (None, "en"),  # Should default to en
        ]
        
        for input_lang, expected in test_cases:
            result = normalize_language_code(input_lang)
            if result == expected:
                logger.info(f"✅ {input_lang} -> {result} (expected {expected})")
            else:
                logger.error(f"❌ {input_lang} -> {result} (expected {expected})")
                
    except Exception as e:
        logger.error(f"Error testing language normalization: {str(e)}")

def test_ollama_health_check():
    """Test the Ollama health check function."""
    logger.info("Testing Ollama health check...")
    
    try:
        from translation.translator import check_ollama_health
        
        result = check_ollama_health()
        if result:
            logger.info("✅ Ollama health check passed")
        else:
            logger.warning("⚠️ Ollama health check failed - this is expected if Ollama is not running")
            
    except Exception as e:
        logger.error(f"Error testing Ollama health check: {str(e)}")

def test_language_detection():
    """Test the language detection function."""
    logger.info("Testing language detection...")
    
    try:
        from translation.translator import detect_language
        
        # Test with English text
        english_text = "Hello, this is a test in English. How are you today?"
        detected = detect_language(english_text)
        logger.info(f"Detected language for English text: {detected}")
        
        # Test with German text
        german_text = "Hallo, das ist ein Test auf Deutsch. Wie geht es dir heute?"
        detected = detect_language(german_text)
        logger.info(f"Detected language for German text: {detected}")
        
    except Exception as e:
        logger.error(f"Error testing language detection: {str(e)}")

def main():
    """Run all tests."""
    logger.info("Starting fix verification tests...")
    
    test_language_normalization()
    test_ollama_health_check()
    test_language_detection()
    
    logger.info("Fix verification tests completed!")

if __name__ == "__main__":
    main()
