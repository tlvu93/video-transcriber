#!/bin/bash
# Consolidated user management script for video-transcriber

# Source common utilities
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/utils.sh"

# Function to display usage
usage() {
    local description="Manage users for video-transcriber"
    local options="  create [-u USER] [-p PASS] [-a]  Create a new user
                       -u USER: Username (required)
                       -p PASS: Password (required)
                       -a: Create as admin user
  create-admin [-u USER] [-p PASS] [-f]  Create an admin user
                       -u USER: Username (default: admin)
                       -p PASS: Password (default: admin)
                       -f: Force creation even if users exist
  list                 List all users in the database"
    local examples="  $0 create -u john -p secret123       # Create regular user
  $0 create -u admin -p admin123 -a    # Create admin user
  $0 create-admin                      # Create default admin user
  $0 create-admin -u superadmin -p strongpass
  $0 create-admin -f                   # Force creation
  $0 list                              # List all users"
    
    display_usage "$description" "$options" "$examples"
}

# Function to create a user
create_user() {
    check_docker_requirements
    
    local USERNAME=""
    local PASSWORD=""
    local IS_ADMIN=false
    
    # Parse arguments
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
            *)
                echo "Unknown argument: $1"
                return 1
                ;;
        esac
    done
    
    # Check if username and password are provided
    if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
        echo "❌ Username and password are required"
        return 1
    fi
    
    # Ensure database is running
    ensure_db_running
    
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
    list_users
}

# Function to create an admin user
create_admin() {
    check_docker_requirements
    
    local USERNAME="admin"
    local PASSWORD="admin"
    local FORCE=false
    
    # Parse arguments
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
            *)
                echo "Unknown argument: $1"
                return 1
                ;;
        esac
    done
    
    # Ensure database is running
    ensure_db_running
    
    # Check if users table exists
    echo "Checking if users table exists..."
    if ! docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -c "\dt users" | grep -q "users"; then
        echo "❌ Users table does not exist. Please run migrations first: ./database.sh migrate"
        exit 1
    fi
    
    # Check if users already exist
    if [[ "$FORCE" != "true" ]]; then
        echo "Checking if users already exist..."
        USER_COUNT=$(docker-compose exec -T postgres psql -U videotranscriber -d videotranscriber -t -c "SELECT COUNT(*) FROM users;" | tr -d '[:space:]')
        
        if [[ "$USER_COUNT" -gt 0 ]]; then
            echo "❌ Users already exist in the database. Use -f to force creation."
            echo "Existing users:"
            list_users
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
    list_users
    
    echo -e "\nYou can now log in with:"
    echo "Username: $USERNAME"
    echo "Password: $PASSWORD"
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
        create)
            create_user "$@"
            ;;
        create-admin)
            create_admin "$@"
            ;;
        list)
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
