#!/bin/bash
# Script to show the status of the database

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

# Check if database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "❌ Database service is not running. Please start it with: ./run_docker.sh"
    exit 1
fi

echo "✅ Database service is running"

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
