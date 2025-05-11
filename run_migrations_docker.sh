#!/bin/bash
# Script to run database migrations in Docker

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

# Check if the database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "Database service is not running. Starting database service..."
    docker-compose up -d postgres
    
    # Wait for database to start
    echo "Waiting for database to start..."
    sleep 10
fi

# Run migrations
echo "Running database migrations..."
docker-compose run --rm api alembic upgrade head

echo "Migrations completed."
