#!/bin/bash
# Script to restore a database backup

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
    echo "Usage: $0 [options] <backup_file>"
    echo ""
    echo "Restore a database backup"
    echo ""
    echo "Arguments:"
    echo "  backup_file        Path to the backup file (.sql or .sql.gz)"
    echo ""
    echo "Options:"
    echo "  -f, --force        Force restore without confirmation"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 ./backups/videotranscriber_backup_20250511_123456.sql.gz"
    echo "  $0 -f ./backups/videotranscriber_backup_20250511_123456.sql"
}

# Parse arguments
FORCE=false
BACKUP_FILE=""

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
            if [[ -z "$BACKUP_FILE" ]]; then
                BACKUP_FILE="$1"
            else
                echo "Unknown argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if backup file is provided
if [[ -z "$BACKUP_FILE" ]]; then
    echo "❌ No backup file provided"
    usage
    exit 1
fi

# Check if backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "❌ Database service is not running. Please start it with: ./run_docker.sh"
    exit 1
fi

# Confirm restore
if [[ "$FORCE" != "true" ]]; then
    echo "⚠️  WARNING: This will overwrite the current database with the backup."
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# Create temporary file for decompressed backup if needed
TEMP_FILE=""
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup file..."
    TEMP_FILE=$(mktemp)
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
    echo "Backup file decompressed."
fi

# Restore backup
echo "Restoring database from backup..."
if cat "$BACKUP_FILE" | docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber; then
    echo "✅ Database restored successfully"
else
    echo "❌ Failed to restore database"
    # Clean up temporary file
    if [[ -n "$TEMP_FILE" ]]; then
        rm -f "$TEMP_FILE"
    fi
    exit 1
fi

# Clean up temporary file
if [[ -n "$TEMP_FILE" ]]; then
    rm -f "$TEMP_FILE"
fi

echo "Database restore completed."
