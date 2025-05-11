#!/bin/bash
# Script to create a new user in the database

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
    echo "Create a new user in the database"
    echo ""
    echo "Options:"
    echo "  -u, --username USERNAME   Username for the new user (required)"
    echo "  -p, --password PASSWORD   Password for the new user (required)"
    echo "  -a, --admin               Create an admin user"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u john -p secret123"
    echo "  $0 -u admin -p admin123 -a"
}

# Parse arguments
USERNAME=""
PASSWORD=""
IS_ADMIN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -p|--password)
            PASSWORD="$2"
            shift 2
            ;;
        -a|--admin)
            IS_ADMIN=true
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

# Check if username and password are provided
if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    echo "❌ Username and password are required"
    usage
    exit 1
fi

# Check if database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "❌ Database service is not running. Please start it with: ./run_docker.sh"
    exit 1
fi

# Create user
echo "Creating user..."
if [[ "$IS_ADMIN" == "true" ]]; then
    ROLE="admin"
else
    ROLE="user"
fi

# Hash the password (using PostgreSQL's crypt function)
HASHED_PASSWORD=$(docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -t -c "SELECT crypt('$PASSWORD', gen_salt('bf'));" | tr -d '[:space:]')

# Insert the user
if docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -c "
INSERT INTO users (username, password_hash, role, created_at, updated_at)
VALUES ('$USERNAME', '$HASHED_PASSWORD', '$ROLE', NOW(), NOW());
"; then
    echo "✅ User '$USERNAME' created successfully with role '$ROLE'"
else
    echo "❌ Failed to create user"
    exit 1
fi

# Show users
echo -e "\nUsers in the database:"
docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
SELECT id, username, role, created_at FROM users ORDER BY id;
"
