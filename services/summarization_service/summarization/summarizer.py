import logging
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import requests
from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document
from langchain_core.language_models.llms import LLM
from langchain_core.prompts import PromptTemplate

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from summarization.config import LLM_HOST, LLM_MODEL

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("summarizer")


logger.info(f"Using LLM at: {LLM_HOST}")
logger.info(f"Using model: {LLM_MODEL}")


class OllamaLLM(LLM):
    """LLM wrapper for Ollama API."""

    model_name: str = LLM_MODEL
    api_url: str = LLM_HOST
    temperature: float = 0.1
    max_tokens: int = 512

    @property
    def _llm_type(self) -> str:
        return "ollama"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Call the Ollama API and return the response."""
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if stop:
            data["stop"] = stop

        logger.info(f"Sending request to Ollama API at {self.api_url}")
        logger.debug(f"Request data: {data}")

        try:
            # Test connectivity to the Ollama API
            try:
                logger.info("Testing connection to Ollama API...")
                conn_test = requests.get(self.api_url.replace("/api/generate", ""), timeout=5)
                logger.info(f"Connection test status: {conn_test.status_code}")
            except Exception as e:
                logger.error(f"Connection test failed: {str(e)}")

            response = requests.post(self.api_url, headers=headers, json=data, timeout=900)
            logger.info(f"Ollama API response status: {response.status_code}")

            response.raise_for_status()
            result = response.json().get("response", "")

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
            error_msg = f"Error calling Ollama API: Request timed out after 900 seconds"
            logger.error(error_msg)
            logger.error(f"Timeout error details: {str(e)}")
            raise
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error calling Ollama API: {e}"
            logger.error(error_msg)
            if e.response.status_code == 404:
                logger.error(
                    f"The model '{self.model_name}' may not be available. Try running: ollama pull {self.model_name}"
                )
            raise
        except Exception as e:
            error_msg = f"Error calling Ollama API: {e}"
            logger.error(error_msg)
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            raise


def get_llm():
    """Initialize and return the LLM client."""
    logger.info("Initializing LLM client...")
    try:
        llm = OllamaLLM(model_name=LLM_MODEL, api_url=LLM_HOST, temperature=0.1, max_tokens=512)
        logger.info("LLM client initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"Error initializing LLM: {e}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None


def create_summary(transcript_text, video_path):
    """
    Create a summary of the transcript using the self-hosted LLM.

    Args:
        transcript_text (str): The full transcript text
        video_path (str): Path to the original video file

    Returns:
        str: The generated summary
    """
    basename = os.path.basename(video_path)
    logger.info(f"🤖 Generating summary for: {basename}")
    logger.info(f"Transcript length: {len(transcript_text)} characters")

    try:
        logger.info("Getting LLM client...")
        llm = get_llm()
        if not llm:
            logger.warning("Failed to initialize LLM, using fallback summary")
            return generate_fallback_summary(transcript_text)

        # Create a document from the transcript
        logger.info("Creating document from transcript")
        doc = Document(page_content=transcript_text)

        try:
            # Define custom prompt for meeting minutes summarization
            logger.info("Creating custom meeting minutes prompt")
            meeting_minutes_prompt = PromptTemplate.from_template(
                """You are an expert meeting-minute writer.

TASK
Summarise the transcript that follows the line ---.

OBJECTIVES
• Detect the meeting's main topic(s) and label them (even if not explicit).
• Identify participants and replace pronouns with names where obvious.
• Capture only information that matters:
   – decisions made
   – action items (owner · task · due date if mentioned)
   – blockers / issues / risks
   – open questions
   – key data points (numbers, URLs, ticket IDs, etc.)
• Discard all filler (greetings, "can you see my screen", navigation clicks, jokes, repeated yes/no, etc.).

OUTPUT FORMAT (Markdown)
1. **One-Sentence Overview** – ≤ 30 words.
2. **Participants** – bullet list *Name (role/affiliation if clear)*.
3. **Key Topics Discussed** – bullets, ≤ 12 words each.
4. **Decisions** – bullets beginning with **✓**.
5. **Action Items** – bullets beginning with **→ Owner – Task – Due/When**.
6. **Open Questions / Risks** – bullets beginning with **?**.
7. **Next Check-point** – "No date mentioned" or the first future date heard.

CONSTRAINTS
• Maximum 120 words per section.
• If something is ambiguous, note it with "[unclear]".
• If a required element is completely missing, output "None stated".
• Before finalising, reread your draft and trim any stray filler or duplicate points.

---

{text}
"""
            )

            # Use LangChain's summarization chain with custom prompt
            logger.info("Creating summarization chain with custom prompt")
            chain = load_summarize_chain(
                llm,
                chain_type="stuff",  # Using "stuff" chain type for single prompt processing
                prompt=meeting_minutes_prompt,
            )

            logger.info("Invoking summarization chain")
            # Updated to use invoke() instead of run() to address deprecation warning
            result = chain.invoke([doc])
            logger.info(f"Summarization chain result type: {type(result)}")

            # Extract the summary text from the result dictionary
            if isinstance(result, dict):
                logger.info(f"Result keys: {result.keys()}")
                # Try common keys used by LangChain for the output
                for key in ["output_text", "text", "summary"]:
                    if key in result:
                        summary = result[key]
                        logger.info(f"Found summary in key: {key}")
                        break
                else:
                    # If none of the expected keys are found, convert the whole dict to a string
                    logger.warning("No expected keys found in result, using string representation")
                    summary = str(result)
            else:
                # If the result is not a dict, convert it to a string
                logger.info("Result is not a dictionary, using string representation")
                summary = str(result)

            logger.info(f"Summary length: {len(summary)} characters")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"⚠️ Ollama API connection error: {e}")
            logger.error(f"Connection error details: {traceback.format_exc()}")
            return generate_fallback_summary(transcript_text)
        except Exception as e:
            logger.error(f"⚠️ Error using LLM for summarization: {e}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return generate_fallback_summary(transcript_text)

        return summary

    except Exception as e:
        error_msg = f"Error generating summary: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return error_msg


def generate_fallback_summary(transcript_text):
    """
    Generate a basic summary when the LLM is not available.

    Args:
        transcript_text (str): The transcript text to summarize

    Returns:
        str: A basic summary of the transcript
    """
    logger.warning("⚠️ Using fallback summary generation method")

    # Extract the first few sentences (up to 500 characters)
    preview = transcript_text[:500].strip()
    if len(transcript_text) > 500:
        preview += "..."

    # Count words and estimate reading time
    word_count = len(transcript_text.split())
    reading_time = round(word_count / 150)  # Assuming 150 words per minute reading speed

    summary = f"""Transcript Preview:
{preview}

Statistics:
- Word count: {word_count} words
- Estimated reading time: {reading_time} minute(s)

Note: This is a basic summary generated because the LLM service (Ollama) was not available.
To generate a full AI summary, please ensure Ollama is running at {LLM_HOST} with the model '{LLM_MODEL}'.
"""
    logger.info("Generated fallback summary")
    return summary


def summarize_from_file(transcript_path, video_path):
    """
    Read a transcript file and create a summary.

    Args:
        transcript_path (str): Path to the transcript file
        video_path (str): Path to the original video file

    Returns:
        str: The generated summary
    """
    logger.info(f"Summarizing from file: {transcript_path}")
    try:
        with open(transcript_path, "r") as f:
            transcript_text = f.read()

        logger.info(f"Read transcript file successfully, length: {len(transcript_text)} characters")
        return create_summary(transcript_text, video_path)

    except Exception as e:
        error_msg = f"Error reading transcript file: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return error_msg
