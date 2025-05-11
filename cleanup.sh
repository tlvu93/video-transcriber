#!/bin/bash
# Script to clean up the Docker environment

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
    echo "Clean up the Docker environment"
    echo ""
    echo "Options:"
    echo "  -a, --all       Remove all containers, volumes, and data"
    echo "  -c, --containers Remove only containers"
    echo "  -v, --volumes   Remove containers and volumes"
    echo "  -d, --data      Remove data directories (videos, transcriptions, summaries)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -a           # Remove all containers, volumes, and data"
    echo "  $0 -c           # Remove only containers"
    echo "  $0 -v           # Remove containers and volumes"
    echo "  $0 -d           # Remove data directories"
}

# Parse arguments
REMOVE_CONTAINERS=false
REMOVE_VOLUMES=false
REMOVE_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            REMOVE_CONTAINERS=true
            REMOVE_VOLUMES=true
            REMOVE_DATA=true
            shift
            ;;
        -c|--containers)
            REMOVE_CONTAINERS=true
            shift
            ;;
        -v|--volumes)
            REMOVE_CONTAINERS=true
            REMOVE_VOLUMES=true
            shift
            ;;
        -d|--data)
            REMOVE_DATA=true
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

# If no options are provided, show usage
if [[ "$REMOVE_CONTAINERS" == "false" && "$REMOVE_VOLUMES" == "false" && "$REMOVE_DATA" == "false" ]]; then
    usage
    exit 0
fi

# Stop containers
if [[ "$REMOVE_CONTAINERS" == "true" ]]; then
    echo "Stopping containers..."
    docker-compose down
fi

# Remove volumes
if [[ "$REMOVE_VOLUMES" == "true" ]]; then
    echo "Removing volumes..."
    docker-compose down -v
fi

# Remove data directories
if [[ "$REMOVE_DATA" == "true" ]]; then
    echo "Removing data directories..."
    
    # Confirm before removing data
    read -p "Are you sure you want to remove all data? This action cannot be undone. (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf data/videos/* data/transcriptions/* data/summaries/* data/db/*
        
        # Keep .gitkeep files
        touch data/videos/.gitkeep data/transcriptions/.gitkeep data/summaries/.gitkeep data/db/.gitkeep
        
        echo "Data directories cleaned."
    else
        echo "Data directories not removed."
    fi
fi

echo "Cleanup completed."
