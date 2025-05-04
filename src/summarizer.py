import os
import sys
import json
import requests
from pathlib import Path
from typing import Any, List, Mapping, Optional
from langchain_core.language_models.llms import LLM
from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import TRANSCRIPT_DIR, SUMMARY_DIR, LLM_HOST, LLM_MODEL

# Ensure summary directory exists
os.makedirs(SUMMARY_DIR, exist_ok=True)

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
            "stream": False
        }
        
        if stop:
            data["stop"] = stop
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=900)  # Increased timeout to 2 minutes
            response.raise_for_status()
            result = response.json().get("response", "")
            
            # Remove any <think> tags and their content
            import re
            result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
            result = result.strip()
            
            return result
        except requests.exceptions.ConnectionError:
            print(f"Error calling Ollama API: Connection refused. Is Ollama running at {self.api_url}?")
            raise
        except requests.exceptions.Timeout:
            print(f"Error calling Ollama API: Request timed out after 120 seconds")
            raise
        except requests.exceptions.HTTPError as e:
            print(f"Error calling Ollama API: {e}")
            if e.response.status_code == 404:
                print(f"The model '{self.model_name}' may not be available. Try running: ollama pull {self.model_name}")
            raise
        except Exception as e:
            print(f"Error calling Ollama API: {e}")
            raise

def get_llm():
    """Initialize and return the LLM client."""
    try:
        llm = OllamaLLM(
            model_name=LLM_MODEL,
            api_url=LLM_HOST,
            temperature=0.1,
            max_tokens=512
        )
        return llm
    except Exception as e:
        print(f"Error initializing LLM: {e}")
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
    print(f"🤖 Generating summary for: {os.path.basename(video_path)}")
    
    try:
        llm = get_llm()
        if not llm:
            return generate_fallback_summary(transcript_text)
        
        # Create a document from the transcript
        doc = Document(page_content=transcript_text)
        
        try:
            # Use LangChain's summarization chain
            chain = load_summarize_chain(llm, chain_type="map_reduce")
            # Updated to use invoke() instead of run() to address deprecation warning
            result = chain.invoke([doc])
            
            # Extract the summary text from the result dictionary
            if isinstance(result, dict):
                # Try common keys used by LangChain for the output
                for key in ["output_text", "text", "summary"]:
                    if key in result:
                        summary = result[key]
                        break
                else:
                    # If none of the expected keys are found, convert the whole dict to a string
                    summary = str(result)
            else:
                # If the result is not a dict, convert it to a string
                summary = str(result)
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Ollama API connection error: {e}")
            return generate_fallback_summary(transcript_text)
        except Exception as e:
            print(f"⚠️ Error using LLM for summarization: {e}")
            return generate_fallback_summary(transcript_text)
        
        # Save the summary to a file
        basename = os.path.splitext(os.path.basename(video_path))[0]
        summary_path = os.path.join(SUMMARY_DIR, f"{basename}_summary.txt")
        
        with open(summary_path, "w") as f:
            f.write(summary)
        
        print(f"✅ Summary saved to: {summary_path}")
        return summary
    
    except Exception as e:
        error_msg = f"Error generating summary: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

def generate_fallback_summary(transcript_text):
    """
    Generate a basic summary when the LLM is not available.
    
    Args:
        transcript_text (str): The transcript text to summarize
    
    Returns:
        str: A basic summary of the transcript
    """
    print("⚠️ Using fallback summary generation method")
    
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
    try:
        with open(transcript_path, "r") as f:
            transcript_text = f.read()
        
        return create_summary(transcript_text, video_path)
    
    except Exception as e:
        error_msg = f"Error reading transcript file: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg
