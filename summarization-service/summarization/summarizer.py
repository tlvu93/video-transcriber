import os
import json
import logging
import requests
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization.summarizer')

# Get environment variables
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-r1")

def generate_summary(transcript_text: str) -> str:
    """
    Generate a summary of a transcript using an LLM.
    
    Args:
        transcript_text: The transcript text to summarize
        
    Returns:
        The generated summary
    """
    logger.info(f"Generating summary using model: {LLM_MODEL}")
    
    # Prepare the prompt
    prompt = f"""
You are an expert summarizer. Your task is to create a concise and informative summary of the following transcript.
Focus on the main topics, key points, and important details. The summary should be well-structured and easy to read.

TRANSCRIPT:
{transcript_text}

SUMMARY:
"""
    
    try:
        # Call the LLM API
        response = call_llm_api(prompt)
        
        # Return the generated summary
        return response
        
    except Exception as e:
        logger.exception(f"Error generating summary: {str(e)}")
        return f"Error generating summary: {str(e)}"

def call_llm_api(prompt: str) -> str:
    """
    Call the LLM API to generate text.
    
    Args:
        prompt: The prompt to send to the LLM
        
    Returns:
        The generated text
    """
    try:
        # Prepare the request payload
        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        # Make the API request
        logger.info(f"Calling LLM API at {LLM_HOST}")
        response = requests.post(LLM_HOST, json=payload)
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        # Return the generated text
        return result.get("response", "")
        
    except requests.exceptions.RequestException as e:
        logger.exception(f"Error calling LLM API: {str(e)}")
        raise Exception(f"Error calling LLM API: {str(e)}")
