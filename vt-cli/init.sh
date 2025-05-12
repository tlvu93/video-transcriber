#!/bin/bash
# Initialization script for video-transcriber

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Initialize the video-transcriber project"
    local options="  -u, --admin-username USERNAME   Username for the admin user (default: admin)
  -p, --admin-password PASSWORD   Password for the admin user (default: admin)
  -f, --force                     Force initialization even if services are already running
  -h, --help                      Show this help message"
    local examples="  $0                              # Initialize with default settings
  $0 -u superadmin -p secret123   # Initialize with custom admin credentials
  $0 -f                           # Force initialization"
    
    display_usage "$description" "$options" "$examples"
}

# Function to initialize the project
initialize() {
    check_docker_requirements
    
    local ADMIN_USERNAME="admin"
    local ADMIN_PASSWORD="admin"
    local FORCE=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--admin-username)
                ADMIN_USERNAME="$2"
                shift 2
                ;;
            -p|--admin-password)
                ADMIN_PASSWORD="$2"
                shift 2
                ;;
            -f|--force)
                FORCE=true
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
    
    # Create necessary directories
    create_data_dirs
    
    # Check if services are already running
    if [[ "$FORCE" != "true" ]]; then
        echo "Checking if services are already running..."
        if docker-compose ps | grep -q "Up"; then
            echo "❌ Services are already running. Use -f to force initialization."
            echo "Running services:"
            docker-compose ps
            exit 1
        fi
    fi
    
    # Build and start the services
    echo "Building and starting services..."
    "$DIR/docker.sh" start
    
    # Run database migrations
    echo "Running database migrations..."
    "$DIR/database.sh" migrate
    
    # Skip the automatic table creation in the API service
    echo "Setting environment variable to skip table creation..."
    export SKIP_DB_INIT=true
    
    # Create admin user
    echo "Creating admin user..."
    "$DIR/user.sh" create-admin -u "$ADMIN_USERNAME" -p "$ADMIN_PASSWORD" -f
    
    # Check status
    echo "Checking service status..."
    "$DIR/docker.sh" status
    
    echo -e "\nInitialization completed."
    echo "You can now access the API at http://localhost:8000"
    echo "Admin credentials:"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: $ADMIN_PASSWORD"
}

# Main function
main() {
    # If no arguments are provided, initialize with default settings
    if [[ $# -eq 0 ]]; then
        initialize
    else
        # Parse command
        case "$1" in
            -h|--help)
                usage
                ;;
            *)
                initialize "$@"
                ;;
        esac
    fi
}

# Execute main function
main "$@"
