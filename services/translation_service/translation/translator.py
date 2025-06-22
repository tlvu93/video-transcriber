import logging
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import requests
from langchain_core.language_models.llms import LLM
from translation.config import LLM_HOST, LLM_MODEL, SUPPORTED_LANGUAGES

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translator")

logger.info(f"Using LLM at: {LLM_HOST}")
logger.info(f"Using model: {LLM_MODEL}")


class OllamaLLM(LLM):
    """LLM wrapper for Ollama API."""

    model_name: str = LLM_MODEL
    api_url: str = LLM_HOST
    temperature: float = 0.1
    max_tokens: int = 2048  # Increased for translations

    @property
    def _llm_type(self) -> str:
        return "ollama"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Call the Ollama API and return the response."""
        headers = {"Content-Type": "application/json"}
        
        # Updated API format for current Ollama versions
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }

        if stop:
            data["options"]["stop"] = stop

        logger.info(f"Sending request to Ollama API at {self.api_url}")
        logger.debug(f"Request data: {data}")

        try:
            # Test connectivity to the Ollama API
            try:
                logger.info("Testing connection to Ollama API...")
                base_url = self.api_url.replace("/api/generate", "")
                conn_test = requests.get(base_url, timeout=5)
                logger.info(f"Connection test status: {conn_test.status_code}")
            except Exception as e:
                logger.error(f"Connection test failed: {str(e)}")

            response = requests.post(self.api_url, headers=headers, json=data, timeout=900)
            logger.info(f"Ollama API response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Ollama API error response: {response.text}")
                response.raise_for_status()

            result_json = response.json()
            result = result_json.get("response", "")

            if not result:
                logger.error(f"Empty response from Ollama API. Full response: {result_json}")
                raise ValueError("Empty response from Ollama API")

            # Remove any <think> tags and their content
            import re
            result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
            result = result.strip()

            logger.info(f"Successfully received response from Ollama API (length: {len(result)})")
            return result
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Error calling Ollama API: Connection refused. Is Ollama running at {self.api_url}?"
            logger.error(error_msg)
            logger.error(f"Connection error details: {str(e)}")
            raise
        except requests.exceptions.Timeout as e:
            error_msg = "Error calling Ollama API: Request timed out after 900 seconds"
            logger.error(error_msg)
            logger.error(f"Timeout error details: {str(e)}")
            raise
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error calling Ollama API: {e}"
            logger.error(error_msg)
            if hasattr(e, 'response') and e.response.status_code == 404:
                logger.error(
                    f"The model '{self.model_name}' may not be available. Try running: ollama pull {self.model_name}"
                )
            elif hasattr(e, 'response') and e.response.status_code == 500:
                logger.error(f"Ollama server error. Response: {e.response.text}")
            raise
        except Exception as e:
            error_msg = f"Error calling Ollama API: {e}"
            logger.error(error_msg)
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise


def check_ollama_health() -> bool:
    """Check if Ollama service is healthy and model is available."""
    try:
        # Check if Ollama is running
        base_url = LLM_HOST.replace("/api/generate", "")
        response = requests.get(base_url, timeout=5)
        if response.status_code != 200:
            logger.error(f"Ollama service not responding. Status: {response.status_code}")
            return False
        
        # Check if model is available
        models_url = base_url + "/api/tags"
        models_response = requests.get(models_url, timeout=5)
        if models_response.status_code == 200:
            models_data = models_response.json()
            available_models = [model["name"] for model in models_data.get("models", [])]
            if LLM_MODEL not in available_models:
                logger.error(f"Model '{LLM_MODEL}' not found in available models: {available_models}")
                return False
        
        logger.info("Ollama health check passed")
        return True
        
    except Exception as e:
        logger.error(f"Ollama health check failed: {str(e)}")
        return False


def get_llm():
    """Initialize and return the LLM client."""
    logger.info("Initializing LLM client...")
    try:
        # Check Ollama health first
        if not check_ollama_health():
            logger.error("Ollama health check failed, cannot initialize LLM")
            return None
            
        llm = OllamaLLM(model_name=LLM_MODEL, api_url=LLM_HOST, temperature=0.1, max_tokens=2048)
        logger.info("LLM client initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None


def translate_text(text: str, source_language: str, target_language: str) -> str:
    """
    Translate text from source language to target language using the local LLM.

    Args:
        text (str): The text to translate
        source_language (str): The source language code (e.g., "en", "de")
        target_language (str): The target language code (e.g., "en", "de")

    Returns:
        str: The translated text
    """
    if source_language == target_language:
        logger.info(f"Source and target languages are the same ({source_language}), returning original text")
        return text

    # Validate languages
    if source_language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Source language {source_language} not in supported languages, defaulting to 'en'")
        source_language = "en"

    if target_language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Target language {target_language} not in supported languages, defaulting to 'en'")
        target_language = "en"

    source_language_name = SUPPORTED_LANGUAGES[source_language]
    target_language_name = SUPPORTED_LANGUAGES[target_language]

    logger.info(f"Translating from {source_language_name} to {target_language_name}")
    logger.info(f"Text length: {len(text)} characters")

    try:
        logger.info("Getting LLM client...")
        llm = get_llm()
        if not llm:
            logger.warning("Failed to initialize LLM, returning original text")
            return text

        # Create translation prompt
        prompt = f"""You are a professional translator. Translate the following transcript from {source_language_name} to {target_language_name}.

IMPORTANT RULES:
1. Prioritize accuracy and natural readability in the target language over literal translation
2. Preserve all speaker identifications
3. Keep all timestamps exactly as they are
4. Do not add or remove any information
5. Keep specialized terminology and technical terms in the original language
6. Translate only the text content, not the structural elements
7. Optimize for readability while maintaining the original meaning

Here is the transcript to translate:

{text}
"""

        # Get translation from LLM
        logger.info("Sending translation request to LLM")
        translation = llm(prompt)
        logger.info(f"Translation completed, length: {len(translation)} characters")

        return translation

    except Exception as e:
        error_msg = f"Error translating text: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return text  # Return original text on error


def translate_segments(segments, source_language: str, target_language: str):
    """
    Translate transcript segments.

    Args:
        segments: List of transcript segments
        source_language (str): The source language code
        target_language (str): The target language code

    Returns:
        List of translated segments
    """
    if not segments:
        return []

    logger.info(f"Translating {len(segments)} segments from {source_language} to {target_language}")

    translated_segments = []

    for segment in segments:
        # Create a copy of the segment
        translated_segment = segment.copy()

        # Translate only the text field
        if "text" in segment and segment["text"]:
            translated_segment["text"] = translate_text(segment["text"], source_language, target_language)

        translated_segments.append(translated_segment)

    logger.info(f"Translated {len(translated_segments)} segments")
    return translated_segments


def detect_language(text: str) -> str:
    """
    Detect the language of the text using the LLM.

    Args:
        text (str): The text to detect language for

    Returns:
        str: The detected language code (e.g., "en", "de")
    """
    try:
        logger.info("Detecting language using LLM...")
        llm = get_llm()
        if not llm:
            logger.warning("Failed to initialize LLM for language detection, defaulting to 'en'")
            return "en"

        # Take a sample of the text for language detection (first 500 characters)
        sample_text = text[:500] if len(text) > 500 else text
        
        # Create language detection prompt
        supported_langs = ", ".join([f"{code} ({name})" for code, name in SUPPORTED_LANGUAGES.items()])
        prompt = f"""Detect the language of the following text. Respond with ONLY the two-letter language code.

Supported languages: {supported_langs}

Text to analyze:
{sample_text}

Language code:"""

        # Get language detection from LLM
        logger.info("Sending language detection request to LLM")
        response = llm(prompt).strip().lower()
        
        # Extract just the language code (in case LLM returns extra text)
        detected_lang = response[:2] if len(response) >= 2 else response
        
        # Validate the detected language is supported
        if detected_lang in SUPPORTED_LANGUAGES:
            logger.info(f"Detected language: {detected_lang} ({SUPPORTED_LANGUAGES[detected_lang]})")
            return detected_lang
        else:
            logger.warning(f"Detected language '{detected_lang}' not in supported languages, defaulting to 'en'")
            return "en"

    except Exception as e:
        logger.error(f"Error detecting language: {str(e)}")
        logger.info("Defaulting to 'en' due to language detection error")
        return "en"
