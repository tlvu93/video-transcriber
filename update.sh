#!/bin/bash
# Script to update Docker images

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

# Function to display usage
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Update Docker images and rebuild services"
    echo ""
    echo "Options:"
    echo "  -p, --pull      Pull latest base images before building"
    echo "  -c, --clean     Clean build (--no-cache)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Update and rebuild services"
    echo "  $0 -p           # Pull latest base images and rebuild services"
    echo "  $0 -c           # Clean build services"
    echo "  $0 -p -c        # Pull latest base images and clean build services"
}

# Parse arguments
PULL=false
CLEAN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--pull)
            PULL=true
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

# Stop services
echo "Stopping services..."
docker-compose down

# Pull latest base images
if [[ "$PULL" == "true" ]]; then
    echo "Pulling latest base images..."
    docker-compose pull
fi

# Build services
echo "Building services..."
if [[ "$CLEAN" == "true" ]]; then
    echo "Using clean build (--no-cache)..."
    docker-compose build --no-cache
else
    docker-compose build
fi

# Start services
echo "Starting services..."
docker-compose up -d

# Check if services are running
echo "Checking if services are running..."
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services are running"
    echo "Check status with: ./check_status.sh"
else
    echo "❌ Services failed to start"
    echo "Check logs with: ./view_logs.sh"
fi
