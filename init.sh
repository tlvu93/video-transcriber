#!/bin/bash
# Script to initialize the project

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
    echo "Initialize the project"
    echo ""
    echo "Options:"
    echo "  -u, --admin-username USERNAME   Username for the admin user (default: admin)"
    echo "  -p, --admin-password PASSWORD   Password for the admin user (default: admin)"
    echo "  -f, --force                     Force initialization even if services are already running"
    echo "  -h, --help                      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Initialize with default settings"
    echo "  $0 -u superadmin -p secret123   # Initialize with custom admin credentials"
    echo "  $0 -f                           # Force initialization"
}

# Parse arguments
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin"
FORCE=false

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
echo "Creating necessary directories..."
mkdir -p data/videos data/transcriptions data/summaries data/db

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
./run_docker.sh

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Run database migrations
echo "Running database migrations..."
./run_migrations_docker.sh

# Create admin user
echo "Creating admin user..."
./create_admin.sh -u "$ADMIN_USERNAME" -p "$ADMIN_PASSWORD" -f

# Check status
echo "Checking service status..."
./check_status.sh

echo -e "\nInitialization completed."
echo "You can now access the API at http://localhost:8000"
echo "Admin credentials:"
echo "  Username: $ADMIN_USERNAME"
echo "  Password: $ADMIN_PASSWORD"
