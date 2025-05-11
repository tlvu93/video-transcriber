#!/bin/bash
# Script to check the status of Docker services

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose."
    exit 1
fi

# Check if services are running
echo "Checking service status..."
docker-compose ps

# Check if database is healthy
echo -e "\nChecking database health..."
if docker-compose ps postgres | grep -q "Up" && docker-compose ps postgres | grep -q "healthy"; then
    echo "✅ Database is running and healthy"
else
    echo "❌ Database is not running or not healthy"
fi

# Check if Ollama is healthy
echo -e "\nChecking Ollama health..."
if docker-compose ps ollama | grep -q "Up" && docker-compose ps ollama | grep -q "healthy"; then
    echo "✅ Ollama is running and healthy"
    
    # Check if model is available
    echo -e "\nChecking if model is available..."
    if docker-compose exec ollama ollama list 2>/dev/null | grep -q "deepseek-r1"; then
        echo "✅ Model deepseek-r1 is available"
    else
        echo "❌ Model deepseek-r1 is not available"
    fi
else
    echo "❌ Ollama is not running or not healthy"
fi

# Check API service
echo -e "\nChecking API service..."
if docker-compose ps api | grep -q "Up"; then
    echo "✅ API service is running"
    
    # Check if API is accessible
    echo -e "\nChecking API accessibility..."
    if curl -s http://localhost:8000/docs > /dev/null; then
        echo "✅ API is accessible at http://localhost:8000"
    else
        echo "❌ API is not accessible"
    fi
else
    echo "❌ API service is not running"
fi

# Check worker services
echo -e "\nChecking worker services..."
if docker-compose ps transcription-worker | grep -q "Up"; then
    echo "✅ Transcription worker is running"
else
    echo "❌ Transcription worker is not running"
fi

if docker-compose ps summarization-worker | grep -q "Up"; then
    echo "✅ Summarization worker is running"
else
    echo "❌ Summarization worker is not running"
fi

echo -e "\nFor detailed logs, use: ./view_logs.sh"
