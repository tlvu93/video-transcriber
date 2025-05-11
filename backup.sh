#!/bin/bash
# Script to create a backup of the database

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
    echo "Create a backup of the database"
    echo ""
    echo "Options:"
    echo "  -o, --output DIR   Output directory for the backup file (default: ./backups)"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Create a backup in ./backups"
    echo "  $0 -o /path/to/dir # Create a backup in /path/to/dir"
}

# Parse arguments
OUTPUT_DIR="./backups"

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
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

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$OUTPUT_DIR/videotranscriber_backup_$TIMESTAMP.sql"

# Check if database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "❌ Database service is not running. Please start it with: ./run_docker.sh"
    exit 1
fi

# Create backup
echo "Creating database backup..."
if docker-compose exec -T postgres pg_dump -U videotranscriber -d videotranscriber > "$BACKUP_FILE"; then
    echo "✅ Backup created successfully: $BACKUP_FILE"
    
    # Create compressed version
    echo "Creating compressed backup..."
    gzip -f "$BACKUP_FILE"
    echo "✅ Compressed backup created: $BACKUP_FILE.gz"
else
    echo "❌ Failed to create backup"
    exit 1
fi

# List backups
echo -e "\nAvailable backups:"
ls -lh "$OUTPUT_DIR"
