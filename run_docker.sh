#!/bin/bash
# Script to run the application in Docker

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

# Create necessary directories
mkdir -p data/videos data/transcriptions data/summaries data/db

# Build and start the services
echo "Building and starting services..."
docker-compose up --build -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Check if services are running
echo "Checking if services are running..."
if ! docker-compose ps | grep -q "Up"; then
    echo "Services failed to start. Check the logs with 'docker-compose logs'."
    exit 1
fi

echo "Services are running. You can access the API at http://localhost:8000"
echo "To view logs, run 'docker-compose logs -f'"
echo "To stop the services, run 'docker-compose down'"
