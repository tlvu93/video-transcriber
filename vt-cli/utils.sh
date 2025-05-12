#!/bin/bash
# Common utility functions for video-transcriber scripts

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker."
        exit 1
    fi
}

# Check if Docker Compose is installed
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose is not installed. Please install Docker Compose."
        exit 1
    fi
}

# Check if Docker and Docker Compose are installed
check_docker_requirements() {
    check_docker
    check_docker_compose
}

# Check if database service is running
check_db_running() {
    echo "Checking if database service is running..."
    if ! docker-compose ps postgres | grep -q "Up"; then
        echo "❌ Database service is not running."
        return 1
    fi
    echo "✅ Database service is running."
    return 0
}

# Start database service if not running
ensure_db_running() {
    if ! check_db_running; then
        echo "Starting database service..."
        docker-compose up -d postgres
        
        # Wait for database to start
        echo "Waiting for database to start..."
        sleep 10
        
        if ! check_db_running; then
            echo "❌ Failed to start database service."
            exit 1
        fi
    fi
}

# Create necessary data directories
create_data_dirs() {
    echo "Creating necessary directories..."
    # Get the project root directory (one level up from the script directory)
    local ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    
    mkdir -p "$ROOT_DIR/data/videos" "$ROOT_DIR/data/transcriptions" "$ROOT_DIR/data/summaries" "$ROOT_DIR/data/db"
    
    # Keep .gitkeep files
    touch "$ROOT_DIR/data/videos/.gitkeep" "$ROOT_DIR/data/transcriptions/.gitkeep" "$ROOT_DIR/data/summaries/.gitkeep" "$ROOT_DIR/data/db/.gitkeep"
}

# Display script usage
display_usage() {
    local script_name=$(basename "$0")
    echo "Usage: $script_name [options]"
    echo ""
    echo "$1"
    echo ""
    echo "Options:"
    echo "$2"
    echo ""
    echo "Examples:"
    echo "$3"
}
