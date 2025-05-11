#!/bin/bash
# Script to fix the database schema issue where videos table is created twice

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
    echo "Fix the database schema issue"
    echo ""
    echo "Options:"
    echo "  -f, --force                     Force restart of services"
    echo "  -h, --help                      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Fix database with default settings"
    echo "  $0 -f                           # Force restart of services"
}

# Parse arguments
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
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

# Stop services if force is true
if [[ "$FORCE" == "true" ]]; then
    echo "Stopping all services..."
    docker-compose down
fi

# Check if the database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "Database service is not running. Starting database service..."
    docker-compose up -d postgres
    
    # Wait for database to start
    echo "Waiting for database to start..."
    sleep 10
fi

# Set environment variable to skip table creation in the API service
export SKIP_DB_INIT=true

# Run migrations to create tables properly
echo "Running database migrations..."
docker-compose run --rm -e SKIP_DB_INIT=true api alembic upgrade head

echo "Migrations completed."

# Ensure pgcrypto extension is installed
echo "Installing pgcrypto extension..."
docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# Restart services with the SKIP_DB_INIT environment variable
echo "Restarting services with SKIP_DB_INIT=true..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Create admin user
echo "Creating admin user..."
./create_admin.sh -u "admin" -p "admin" -f

echo -e "\nDatabase fix completed."
echo "You can now access the API at http://localhost:8000"
echo "Admin credentials:"
echo "  Username: admin"
echo "  Password: admin"
