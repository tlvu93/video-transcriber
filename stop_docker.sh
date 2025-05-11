#!/bin/bash
# Script to stop the Docker services

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

# Stop the services
echo "Stopping services..."
docker-compose down

echo "Services stopped."
