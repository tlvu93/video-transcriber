#!/bin/bash
# Script to run the application locally

# Set up environment variables
export DATABASE_URL="postgresql://videotranscriber:videotranscriber@localhost/videotranscriber"
export LLM_HOST="http://localhost:11434/api/generate"
export LLM_MODEL="deepseek-r1"

# Check if PostgreSQL is running
echo "Checking PostgreSQL..."
if ! pg_isready -h localhost -p 5432 -U videotranscriber > /dev/null 2>&1; then
    echo "PostgreSQL is not running or not accessible. Please start PostgreSQL."
    exit 1
fi

# Check if Ollama is running
echo "Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama is not running. Please start Ollama."
    exit 1
fi

# Check if the model is available
echo "Checking if model is available..."
if ! curl -s http://localhost:11434/api/tags | grep -q "$LLM_MODEL"; then
    echo "Model $LLM_MODEL is not available. Pulling model..."
    ollama pull "$LLM_MODEL"
fi

# Run migrations
echo "Running database migrations..."
python run_migrations.py

# Create necessary directories
mkdir -p data/videos data/transcriptions data/summaries data/db

# Start the application
echo "Starting application..."
python src/main.py
