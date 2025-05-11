#!/bin/bash
# Script to create an initial admin user in the database

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
    echo "Create an initial admin user in the database"
    echo ""
    echo "Options:"
    echo "  -u, --username USERNAME   Username for the admin user (default: admin)"
    echo "  -p, --password PASSWORD   Password for the admin user (default: admin)"
    echo "  -f, --force               Force creation even if users already exist"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                        # Create admin user with default credentials"
    echo "  $0 -u superadmin -p secret123"
    echo "  $0 -f                     # Force creation even if users exist"
}

# Parse arguments
USERNAME="admin"
PASSWORD="admin"
FORCE=false

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

# Check if database service is running
echo "Checking if database service is running..."
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "❌ Database service is not running. Please start it with: ./run_docker.sh"
    exit 1
fi

# Check if users table exists
echo "Checking if users table exists..."
if ! docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -c "\dt users" | grep -q "users"; then
    echo "❌ Users table does not exist. Please run migrations first: ./run_migrations_docker.sh"
    exit 1
fi

# Check if users already exist
if [[ "$FORCE" != "true" ]]; then
    echo "Checking if users already exist..."
    USER_COUNT=$(docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -t -c "SELECT COUNT(*) FROM users;" | tr -d '[:space:]')
    
    if [[ "$USER_COUNT" -gt 0 ]]; then
        echo "❌ Users already exist in the database. Use -f to force creation."
        echo "Existing users:"
        docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "SELECT id, username, role, created_at FROM users ORDER BY id;"
        exit 1
    fi
fi

# Create admin user with UUID and password hash directly in SQL
echo "Creating admin user..."
if docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -c "
INSERT INTO users (id, username, password_hash, role, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  '$USERNAME', 
  crypt('$PASSWORD', gen_salt('bf')), 
  'admin', 
  NOW(), 
  NOW()
);
"; then
    echo "✅ Admin user '$USERNAME' created successfully"
else
    echo "❌ Failed to create admin user"
    exit 1
fi

# Show users
echo -e "\nUsers in the database:"
docker-compose exec postgres psql -U videotranscriber -d videotranscriber -c "
SELECT id, username, role, created_at FROM users ORDER BY id;
"

echo -e "\nYou can now log in with:"
echo "Username: $USERNAME"
echo "Password: $PASSWORD"
