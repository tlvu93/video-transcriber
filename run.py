#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import importlib.util
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run')

def import_module(module_path, module_name):
    """Import a module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run_api():
    """Run the API server."""
    logger.info("Starting API server...")
    api_main = import_module("api-service/api/main.py", "api_main")
    api_main.main()

def run_transcription_worker():
    """Run the transcription worker."""
    logger.info("Starting transcription worker...")
    transcription_worker = import_module(
        "transcription-service/transcription/transcription_worker.py", 
        "transcription_worker"
    )
    transcription_worker.start_worker()

def run_summarization_worker():
    """Run the summarization worker."""
    logger.info("Starting summarization worker...")
    summarization_worker = import_module(
        "summarization-service/summarization/summarization_worker.py", 
        "summarization_worker"
    )
    summarization_worker.start_worker()

def run_watcher():
    """Run the file watcher."""
    logger.info("Starting file watcher...")
    watcher = import_module("watcher-service/watcher/watcher.py", "watcher")
    watcher.start_watching()

def run_processor(filepath):
    """Run the processor on a specific file."""
    logger.info(f"Processing file: {filepath}")
    processor = import_module("transcription-service/transcription/processor.py", "processor")
    result = processor.process_video(filepath)
    logger.info(f"Processing result: {result}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run Video Transcriber components')
    parser.add_argument('component', choices=['api', 'transcription', 'summarization', 'watcher', 'processor'],
                        help='Component to run')
    parser.add_argument('--file', help='File to process (only for processor component)')
    
    args = parser.parse_args()
    
    if args.component == 'api':
        run_api()
    elif args.component == 'transcription':
        run_transcription_worker()
    elif args.component == 'summarization':
        run_summarization_worker()
    elif args.component == 'watcher':
        run_watcher()
    elif args.component == 'processor':
        if not args.file:
            logger.error("File path is required for processor component")
            parser.print_help()
            sys.exit(1)
        run_processor(args.file)
    else:
        logger.error(f"Unknown component: {args.component}")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
