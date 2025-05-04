# Video Transcriber with Auto-Processing

This application automatically transcribes video files placed in the `data/videos` directory. It uses the Whisper model for transcription and saves the results in the `data/transcriptions` directory.

## Features

- Automatic detection of new or modified video files
- Transcription of video content to text
- Generation of SRT subtitle files
- Metadata extraction
- Deduplication based on file hash

## Requirements

The following packages are required:

- watchdog
- openai-whisper
- ffmpeg-python
- rich
- requests

Install them using:

```
pip install -r requirements.txt
```

You also need to have ffmpeg installed on your system.

## Usage

1. Place your video files in the `data/videos` directory
2. Run the watcher script:

```
python src/watcher.py
```

3. The script will automatically process any existing videos and then watch for new or modified videos
4. Transcriptions will be saved in the `data/transcriptions` directory

## File Structure

- `data/videos/`: Place your video files here
- `data/transcriptions/`: Transcription results are saved here
- `data/db/`: Database files for tracking processed videos

## Scripts

- `src/watcher.py`: Main script that watches for file changes and triggers processing
- `src/main.py`: Contains the main processing logic
- `src/processor.py`: Handles video transcription
- `src/database.py`: Manages the database of processed files
- `src/utils.py`: Utility functions
- `src/config.py`: Configuration settings

## Stopping the Watcher

Press `Ctrl+C` in the terminal to stop the watcher script.
