#!/bin/bash
# Consolidated Docker management script for video-transcriber

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Manage Docker services for video-transcriber"
    local options="  start                Start all services
  stop                 Stop all services
  restart [service]    Restart all services or a specific service
  status               Show status of all services
  logs [service] [-f]  View logs of all services or a specific service
                       -f: Follow log output
                       -t N: Show only the last N lines
  update [-p] [-c]     Update and rebuild services
                       -p: Pull latest base images
                       -c: Clean build (--no-cache)
  clean [-a|-c|-v|-d]  Clean up the Docker environment
                       -a: Remove all containers, volumes, and data
                       -c: Remove only containers
                       -v: Remove containers and volumes
                       -d: Remove data directories"
    local examples="  $0 start            # Start all services
  $0 stop             # Stop all services
  $0 restart          # Restart all services
  $0 restart api      # Restart only the API service
  $0 status           # Show status of all services
  $0 logs             # View logs of all services
  $0 logs api         # View logs of the API service
  $0 logs api -f      # Follow logs of the API service
  $0 update           # Update and rebuild services
  $0 update -p -c     # Pull latest images and clean build
  $0 clean -c         # Remove only containers"
    
    display_usage "$description" "$options" "$examples"
}

# Function to start services
start_services() {
    check_docker_requirements
    
    # Create necessary directories
    create_data_dirs
    
    # Build and start the services
    echo "Building and starting services..."
    docker-compose up --build -d
    
    # Wait for services to start
    echo "Waiting for services to start..."
    sleep 10
    
    # Check if services are running
    echo "Checking if services are running..."
    if ! docker-compose ps | grep -q "Up"; then
        echo "❌ Services failed to start. Check the logs with '$0 logs'"
        exit 1
    fi
    
    echo "✅ Services are running. You can access the API at http://localhost:8000"
    echo "To view logs, run '$0 logs'"
    echo "To stop the services, run '$0 stop'"
}

# Function to stop services
stop_services() {
    check_docker_requirements
    
    # Stop the services
    echo "Stopping services..."
    docker-compose down
    
    echo "✅ Services stopped."
}

# Function to restart services
restart_services() {
    check_docker_requirements
    
    local SERVICE="$1"
    
    # Restart services
    if [[ -n "$SERVICE" ]]; then
        echo "Restarting $SERVICE service..."
        docker-compose restart "$SERVICE"
        
        # Check if service restarted successfully
        if docker-compose ps "$SERVICE" | grep -q "Up"; then
            echo "✅ $SERVICE service restarted successfully"
        else
            echo "❌ Failed to restart $SERVICE service"
            echo "Check logs with: $0 logs $SERVICE"
        fi
    else
        echo "Restarting all services..."
        docker-compose restart
        
        # Check if services restarted successfully
        if docker-compose ps | grep -q "Up"; then
            echo "✅ Services restarted successfully"
        else
            echo "❌ Some services failed to restart"
            echo "Check status with: $0 status"
            echo "Check logs with: $0 logs"
        fi
    fi
}

# Function to check status
check_status() {
    check_docker_requirements
    
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
    
    echo -e "\nFor detailed logs, use: $0 logs"
}

# Function to view logs
view_logs() {
    check_docker_requirements
    
    local SERVICE=""
    local FOLLOW=""
    local TAIL=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
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
                    return 1
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
}

# Function to update services
update_services() {
    check_docker_requirements
    
    local PULL=false
    local CLEAN=false
    
    # Parse arguments
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
            *)
                echo "Unknown argument: $1"
                return 1
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
        echo "Check status with: $0 status"
    else
        echo "❌ Services failed to start"
        echo "Check logs with: $0 logs"
    fi
}

# Function to clean up
cleanup() {
    check_docker_requirements
    
    local REMOVE_CONTAINERS=false
    local REMOVE_VOLUMES=false
    local REMOVE_DATA=false
    
    # Parse arguments
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
            *)
                echo "Unknown argument: $1"
                return 1
                ;;
        esac
    done
    
    # If no options are provided, show usage
    if [[ "$REMOVE_CONTAINERS" == "false" && "$REMOVE_VOLUMES" == "false" && "$REMOVE_DATA" == "false" ]]; then
        echo "No cleanup options specified."
        echo "Use -c to remove containers, -v to remove volumes, -d to remove data, or -a for all."
        return 1
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
}

# Main function
main() {
    # Check if at least one argument is provided
    if [[ $# -lt 1 ]]; then
        usage
        exit 1
    fi
    
    # Parse command
    COMMAND="$1"
    shift
    
    case "$COMMAND" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services "$@"
            ;;
        status)
            check_status
            ;;
        logs)
            view_logs "$@"
            ;;
        update)
            update_services "$@"
            ;;
        clean)
            cleanup "$@"
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
