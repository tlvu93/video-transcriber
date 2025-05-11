#!/bin/bash
# Script to restart Docker services

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
    echo "Usage: $0 [service]"
    echo ""
    echo "Restart Docker services"
    echo ""
    echo "Arguments:"
    echo "  service   Service name (api, transcription-worker, summarization-worker, postgres, ollama)"
    echo "            If not specified, all services will be restarted"
    echo ""
    echo "Examples:"
    echo "  $0                    # Restart all services"
    echo "  $0 api                # Restart only the API service"
}

# Parse arguments
SERVICE=""

if [[ $# -gt 0 ]]; then
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        *)
            SERVICE="$1"
            ;;
    esac
fi

# Restart services
if [[ -n "$SERVICE" ]]; then
    echo "Restarting $SERVICE service..."
    docker-compose restart $SERVICE
    
    # Check if service restarted successfully
    if docker-compose ps $SERVICE | grep -q "Up"; then
        echo "✅ $SERVICE service restarted successfully"
    else
        echo "❌ Failed to restart $SERVICE service"
        echo "Check logs with: ./view_logs.sh $SERVICE"
    fi
else
    echo "Restarting all services..."
    docker-compose restart
    
    # Check if services restarted successfully
    if docker-compose ps | grep -q "Up"; then
        echo "✅ Services restarted successfully"
    else
        echo "❌ Some services failed to restart"
        echo "Check status with: ./check_status.sh"
        echo "Check logs with: ./view_logs.sh"
    fi
fi
