#!/bin/bash
# Setup script for standalone transcription service testing

set -e

echo "🚀 Setting up standalone transcription service testing environment..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Please run this script from the transcription-service directory."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source ./venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install the common package first (in development mode)
echo "📚 Installing common package..."
cd ../../common
pip install -e .
cd ../services/transcription-service

# Install transcription service dependencies
echo "📦 Installing transcription service dependencies..."
pip install -e ".[all]"

# Install additional testing dependencies
echo "🧪 Installing testing dependencies..."
pip install pytest soundfile numpy

echo "✅ Setup complete!"
echo ""
echo "To test the transcription service standalone:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the standalone test: python standalone_test.py"
echo "3. Or test with an audio file: python standalone_test.py /path/to/audio.wav"
echo ""
echo "To run the original WhisperX test:"
echo "python test_whisperx.py [optional_audio_file]"
