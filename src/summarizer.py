import os
import sys
import json
import requests
from pathlib import Path
from typing import Any, List, Mapping, Optional
from langchain.llms.base import LLM
from langchain.chains.summarize import load_summarize_chain
from langchain.docstore.document import Document

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
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Error calling Ollama API: {e}")
            return f"Error: {str(e)}"

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
            return "Error: Could not initialize LLM"
        
        # Create a document from the transcript
        doc = Document(page_content=transcript_text)
        
        # Use LangChain's summarization chain
        chain = load_summarize_chain(llm, chain_type="map_reduce")
        summary = chain.run([doc])
        
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
