import hashlib
import subprocess
import json
import time
import os

def get_file_hash(filepath, max_retries=5, retry_delay=2):
    """
    Calculate the SHA-256 hash of a file with retry mechanism for handling locked files.
    
    Args:
        filepath: Path to the file
        max_retries: Maximum number of retry attempts
        retry_delay: Delay in seconds between retries
        
    Returns:
        SHA-256 hash of the file as a hexadecimal string
        
    Raises:
        Exception: If the file cannot be accessed after all retry attempts
    """
    retries = 0
    while retries < max_retries:
        try:
            # Check if file exists and is accessible
            if not os.path.exists(filepath):
                print(f"⚠️ File not found: {filepath}")
                return None
                
            # Check if file is still being written (size changing)
            initial_size = os.path.getsize(filepath)
            time.sleep(0.5)  # Brief delay to check if size changes
            if initial_size != os.path.getsize(filepath):
                print(f"⚠️ File is still being written: {filepath}")
                time.sleep(retry_delay)
                retries += 1
                continue
                
            # Try to open and hash the file
            hasher = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
            
        except (PermissionError, OSError) as e:
            print(f"⚠️ Cannot access file (attempt {retries+1}/{max_retries}): {filepath}")
            print(f"   Error: {str(e)}")
            time.sleep(retry_delay)
            retries += 1
    
    print(f"❌ Failed to access file after {max_retries} attempts: {filepath}")
    return None

def get_video_metadata(filepath):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
