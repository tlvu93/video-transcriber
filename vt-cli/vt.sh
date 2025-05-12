#!/bin/bash
# Main script for video-transcriber

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Video Transcriber - Main Command"
    local options="  init [options]           Initialize the project
  docker <command>        Manage Docker services
  db <command>            Manage database
  user <command>          Manage users
  local                   Run locally (without Docker)
  help                    Show this help message"
    local examples="  ./vt init                  # Initialize with default settings
  ./vt init -u admin -p pass  # Initialize with custom admin
  ./vt docker start          # Start Docker services
  ./vt docker logs api       # View logs of API service
  ./vt db migrate            # Run database migrations
  ./vt db backup             # Create database backup
  ./vt user create-admin     # Create admin user
  ./vt local                 # Run locally"
    
    display_usage "$description" "$options" "$examples"
    
    echo -e "\nFor more detailed help on a specific command, run:"
    echo "  ./vt <command> --help"
    echo ""
    echo "For full documentation, see vt-cli/SCRIPTS.md"
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
        init)
            "$DIR/init.sh" "$@"
            ;;
        docker)
            "$DIR/docker.sh" "$@"
            ;;
        db)
            "$DIR/database.sh" "$@"
            ;;
        user)
            "$DIR/user.sh" "$@"
            ;;
        local)
            "$DIR/local.sh" "$@"
            ;;
        help)
            usage
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
