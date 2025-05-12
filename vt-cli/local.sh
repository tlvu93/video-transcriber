#!/bin/bash
# Script to run the application locally (without Docker)

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Run the video-transcriber application locally (without Docker)"
    local options="  -h, --help      Show this help message"
    local examples="  $0             # Run the application locally"
    
    display_usage "$description" "$options" "$examples"
}

# Function to run the application locally
run_local() {
    # Set up environment variables
    export DATABASE_URL="postgresql://videotranscriber:videotranscriber@localhost/videotranscriber"
    export LLM_HOST="http://localhost:11434/api/generate"
    export LLM_MODEL="deepseek-r1"
    
    # Check if PostgreSQL is running
    echo "Checking PostgreSQL..."
    if ! pg_isready -h localhost -p 5432 -U videotranscriber > /dev/null 2>&1; then
        echo "❌ PostgreSQL is not running or not accessible. Please start PostgreSQL."
        exit 1
    fi
    
    # Check if Ollama is running
    echo "Checking Ollama..."
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "❌ Ollama is not running. Please start Ollama."
        exit 1
    fi
    
    # Check if the model is available
    echo "Checking if model is available..."
    if ! curl -s http://localhost:11434/api/tags | grep -q "$LLM_MODEL"; then
        echo "❌ Model $LLM_MODEL is not available. Pulling model..."
        ollama pull "$LLM_MODEL"
    fi
    
    # Run migrations
    echo "Running database migrations..."
    python run_migrations.py
    
    # Create necessary directories
    create_data_dirs
    
    # Start the application
    echo "Starting application..."
    python run.py
}

# Main function
main() {
    # Parse command
    if [[ $# -eq 0 ]]; then
        run_local
    else
        case "$1" in
            -h|--help)
                usage
                ;;
            *)
                echo "Unknown argument: $1"
                usage
                exit 1
                ;;
        esac
    fi
}

# Execute main function
main "$@"
