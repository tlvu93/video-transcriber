#!/bin/bash
# Consolidated database management script for video-transcriber

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Manage database for video-transcriber"
    local options="  migrate              Run database migrations
  status               Show database status and statistics
  backup [-o DIR]      Create a database backup
                       -o DIR: Output directory (default: ./backups)
  restore FILE [-f]    Restore a database backup
                       -f: Force restore without confirmation
  fix                  Fix database schema issues
  users                List users in the database"
    local examples="  $0 migrate          # Run database migrations
  $0 status           # Show database status
  $0 backup           # Create a backup in ./backups
  $0 backup -o /path  # Create a backup in /path
  $0 restore ./backups/videotranscriber_backup_20250511_123456.sql.gz
  $0 restore -f ./backups/videotranscriber_backup_20250511_123456.sql
  $0 fix              # Fix database schema issues
  $0 users            # List users in the database"
    
    display_usage "$description" "$options" "$examples"
}

# Function to run migrations
run_migrations() {
    check_docker_requirements
    
    # Ensure database is running
    ensure_db_running
    
    # Run migrations
    echo "Running database migrations..."
    if docker-compose run --rm api alembic upgrade head; then
        echo "✅ Migrations completed successfully."
    else
        echo "❌ Migrations failed."
        exit 1
    fi
}

# Function to show database status
show_db_status() {
    check_docker_requirements
    
    # Ensure database is running
    ensure_db_running
    
    # Show database size
    echo -e "\nDatabase size:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "SELECT pg_size_pretty(pg_database_size('videotranscriber')) as db_size;"
    
    # Show table counts
    echo -e "\nTable row counts:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
    WITH tables AS (
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
    )
    SELECT
        'videos' as table_name,
        (SELECT count(*) FROM videos) as row_count
    UNION ALL
    SELECT
        'transcripts' as table_name,
        (SELECT count(*) FROM transcripts) as row_count
    UNION ALL
    SELECT
        'summaries' as table_name,
        (SELECT count(*) FROM summaries) as row_count
    UNION ALL
    SELECT
        'transcription_jobs' as table_name,
        (SELECT count(*) FROM transcription_jobs) as row_count
    UNION ALL
    SELECT
        'summarization_jobs' as table_name,
        (SELECT count(*) FROM summarization_jobs) as row_count
    ORDER BY
        table_name;
    "
    
    # Show recent jobs
    echo -e "\nRecent transcription jobs:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
    SELECT
        id,
        video_id,
        status,
        created_at,
        updated_at
    FROM
        transcription_jobs
    ORDER BY
        created_at DESC
    LIMIT 5;
    "
    
    echo -e "\nRecent summarization jobs:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
    SELECT
        id,
        transcript_id,
        status,
        created_at,
        updated_at
    FROM
        summarization_jobs
    ORDER BY
        created_at DESC
    LIMIT 5;
    "
    
    # Show database stats
    echo -e "\nDatabase statistics:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
    SELECT
        sum(numbackends) as connections,
        sum(xact_commit) as commits,
        sum(xact_rollback) as rollbacks,
        sum(blks_read) as blocks_read,
        sum(blks_hit) as blocks_hit,
        sum(tup_returned) as rows_returned,
        sum(tup_fetched) as rows_fetched,
        sum(tup_inserted) as rows_inserted,
        sum(tup_updated) as rows_updated,
        sum(tup_deleted) as rows_deleted
    FROM
        pg_stat_database;
    "
}

# Function to backup database
backup_db() {
    check_docker_requirements
    
    local OUTPUT_DIR="./backups"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            *)
                echo "Unknown argument: $1"
                return 1
                ;;
        esac
    done
    
    # Create output directory if it doesn't exist
    mkdir -p "$OUTPUT_DIR"
    
    # Generate backup filename with timestamp
    local TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    local BACKUP_FILE="$OUTPUT_DIR/videotranscriber_backup_$TIMESTAMP.sql"
    
    # Ensure database is running
    ensure_db_running
    
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
}

# Function to restore database
restore_db() {
    check_docker_requirements
    
    local FORCE=false
    local BACKUP_FILE=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                FORCE=true
                shift
                ;;
            *)
                if [[ -z "$BACKUP_FILE" ]]; then
                    BACKUP_FILE="$1"
                else
                    echo "Unknown argument: $1"
                    return 1
                fi
                shift
                ;;
        esac
    done
    
    # Check if backup file is provided
    if [[ -z "$BACKUP_FILE" ]]; then
        echo "❌ No backup file provided"
        return 1
    fi
    
    # Check if backup file exists
    if [[ ! -f "$BACKUP_FILE" ]]; then
        echo "❌ Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    # Ensure database is running
    ensure_db_running
    
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
    local TEMP_FILE=""
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
}

# Function to fix database
fix_database() {
    check_docker_requirements
    
    # Ensure database is running
    ensure_db_running
    
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
    
    echo -e "\nDatabase fix completed."
    echo "You can now access the API at http://localhost:8000"
}

# Function to list users
list_users() {
    check_docker_requirements
    
    # Ensure database is running
    ensure_db_running
    
    # Show users
    echo "Users in the database:"
    docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
    SELECT id, username, role, created_at FROM users ORDER BY id;
    "
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
        migrate)
            run_migrations
            ;;
        status)
            show_db_status
            ;;
        backup)
            backup_db "$@"
            ;;
        restore)
            restore_db "$@"
            ;;
        fix)
            fix_database
            ;;
        users)
            list_users
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
