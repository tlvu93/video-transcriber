#!/bin/bash
# Script to view logs of Docker services

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
    echo "Usage: $0 [service] [options]"
    echo ""
    echo "View logs of Docker services"
    echo ""
    echo "Arguments:"
    echo "  service   Service name (api, transcription-worker, summarization-worker, postgres, ollama)"
    echo "            If not specified, logs of all services will be shown"
    echo ""
    echo "Options:"
    echo "  -f, --follow   Follow log output"
    echo "  -t, --tail N   Show only the last N lines"
    echo "  -h, --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Show logs of all services"
    echo "  $0 api                # Show logs of the API service"
    echo "  $0 api -f             # Follow logs of the API service"
    echo "  $0 api -t 100         # Show last 100 lines of the API service logs"
    echo "  $0 -f                 # Follow logs of all services"
}

# Parse arguments
SERVICE=""
FOLLOW=""
TAIL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -f|--follow)
            FOLLOW="-f"
            shift
            ;;
        -t|--tail)
            TAIL="--tail $2"
            shift 2
            ;;
        *)
            if [[ -z "$SERVICE" ]]; then
                SERVICE="$1"
            else
                echo "Unknown argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# View logs
if [[ -n "$SERVICE" ]]; then
    echo "Viewing logs of $SERVICE service..."
    docker-compose logs $FOLLOW $TAIL $SERVICE
else
    echo "Viewing logs of all services..."
    docker-compose logs $FOLLOW $TAIL
fi
