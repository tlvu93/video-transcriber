# Standalone Transcription Service Testing

This guide explains how to test the transcription service independently without running the full application stack.

## Overview

The transcription service can be tested in several ways:

1. **Standalone Python Testing** - Run tests directly with Python
2. **Docker-based Testing** - Run tests in an isolated Docker container
3. **WhisperX Integration Testing** - Test the core WhisperX functionality

## Prerequisites

- Python 3.9+
- Docker (for Docker-based testing)
- Audio/video files for testing (optional)

## Method 1: Standalone Python Testing

### Setup

1. Navigate to the transcription service directory:

   ```bash
   cd services/transcription-service
   ```

2. Run the setup script:

   ```bash
   ./setup_standalone.sh
   ```

   This will:

   - Create a virtual environment
   - Install all dependencies
   - Set up the common package

### Running Tests

1. Activate the virtual environment:

   ```bash
   source venv/bin/activate
   ```

2. Run the comprehensive standalone test:

   ```bash
   python standalone_test.py
   ```

3. Test with your own audio file:

   ```bash
   python standalone_test.py /path/to/your/audio.wav
   ```

4. Run the original WhisperX test:
   ```bash
   python test_whisperx.py
   ```

### What the Tests Cover

The `standalone_test.py` script tests:

- ✅ **Import Testing** - Verifies all required modules can be imported
- ✅ **WhisperX Basic Functionality** - Tests model loading and basic operations
- ✅ **Video File Discovery** - Tests the file finding functionality
- ✅ **Utility Functions** - Tests timestamp formatting and other utilities
- ✅ **Audio Transcription** - Full transcription pipeline with real audio

## Method 2: Docker-based Testing

### Setup

1. Navigate to the transcription service directory:

   ```bash
   cd services/transcription-service
   ```

2. Create test directories:

   ```bash
   mkdir -p test_audio test_results
   ```

3. (Optional) Place test audio files in the `test_audio` directory

### Running Docker Tests

1. Build and run the standalone test:

   ```bash
   docker-compose -f docker-compose.standalone.yml up --build
   ```

2. Run specific tests:

   ```bash
   # Run the comprehensive test
   docker-compose -f docker-compose.standalone.yml run transcription-test python standalone_test.py

   # Run WhisperX test
   docker-compose -f docker-compose.standalone.yml run transcription-test python test_whisperx.py

   # Test with a specific audio file
   docker-compose -f docker-compose.standalone.yml run transcription-test python standalone_test.py /app/test_audio/your_file.wav
   ```

3. Clean up:
   ```bash
   docker-compose -f docker-compose.standalone.yml down
   ```

## Method 3: Manual Testing

You can also test individual components manually:

### Test WhisperX Installation

```python
import torch
import whisperx

# Check device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load model
model = whisperx.load_model("base", device)
print("Model loaded successfully!")
```

### Test Transcription Pipeline

```python
import whisperx

# Load model and audio
model = whisperx.load_model("base", "cpu")
audio = whisperx.load_audio("path/to/audio.wav")

# Transcribe
result = model.transcribe(audio)
print(f"Transcription: {result['text']}")
```

### Test Project Components

```python
from transcription.processor import find_video_file, format_srt_timestamp
from transcription.config import VIDEO_DIRS

# Test file discovery
video_path = find_video_file("test.mp4")

# Test timestamp formatting
timestamp = format_srt_timestamp(61.5)  # Should return "00:01:01,500"
```

## Testing with Your Own Audio/Video Files

### Supported Formats

The transcription service supports various audio and video formats:

- Audio: WAV, MP3, FLAC, M4A
- Video: MP4, AVI, MOV, MKV (audio will be extracted)

### Adding Test Files

1. **For Python testing**: Place files in `data/videos/` or any directory
2. **For Docker testing**: Place files in `test_audio/` directory

### Example Test Commands

```bash
# Test with a WAV file
python standalone_test.py /path/to/speech.wav

# Test with a video file (audio will be extracted)
python standalone_test.py /path/to/video.mp4

# Docker testing
docker-compose -f docker-compose.standalone.yml run transcription-test python standalone_test.py /app/test_audio/speech.wav
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure all dependencies are installed

   ```bash
   pip install -e ".[all]"
   ```

2. **CUDA Issues**: If you have GPU but getting CPU warnings:

   ```bash
   # Check CUDA availability
   python -c "import torch; print(torch.cuda.is_available())"
   ```

3. **Memory Issues**: For large files, reduce batch size:

   ```python
   result = model.transcribe(audio, batch_size=8)  # Default is 16
   ```

4. **Model Download Issues**: First run may take time to download models:
   ```bash
   # Models are cached in ~/.cache/whisperx/
   ls ~/.cache/whisperx/
   ```

### Performance Tips

- **Use GPU**: Install CUDA-compatible PyTorch for faster processing
- **Batch Size**: Adjust based on available memory
- **Model Size**: Use larger models (small, medium, large) for better accuracy
- **Audio Quality**: Higher quality audio gives better results

## Environment Variables

You can customize behavior with environment variables:

```bash
# Set custom video directories
export VIDEO_DIRS="/path/to/videos1,/path/to/videos2"

# Set API URL (not used in standalone mode)
export API_URL="http://localhost:8000"
```

## Integration with Full Stack

Once standalone testing is successful, the transcription service can be integrated with the full application stack:

1. **API Service**: Provides job management and database operations
2. **RabbitMQ**: Handles event messaging between services
3. **Watcher Service**: Monitors for new video files
4. **Summarization Service**: Processes transcription results

To run the full stack:

```bash
cd ../../  # Go to project root
docker-compose up
```

## Next Steps

After successful standalone testing:

1. Test with the full application stack
2. Monitor performance with real workloads
3. Adjust configuration based on your hardware
4. Set up production deployment

## Support

For issues or questions:

1. Check the logs for detailed error messages
2. Verify all dependencies are correctly installed
3. Test with smaller audio files first
4. Check GPU/CUDA setup if using GPU acceleration
