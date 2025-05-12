# Video Transcriber Scripts

This document provides an overview of the scripts available for managing the Video Transcriber application.

## Unified Command Interface

The `vt.sh` script provides a unified interface to all other scripts. A symlink `vt` is also available for convenience:

```bash
# Initialize the project
./vt init

# Manage Docker services
./vt docker start
./vt docker logs api

# Manage database
./vt db migrate
./vt db backup

# Manage users
./vt user create-admin
./vt user list

# Run locally
./vt local

# Get help
./vt help
```

## Script Structure

The scripts have been organized into a modular structure:

- `vt.sh`: Main command interface
- `utils.sh`: Common utility functions used by other scripts
- `docker.sh`: Docker service management
- `database.sh`: Database management
- `user.sh`: User management
- `init.sh`: Project initialization
- `local.sh`: Run the application locally (without Docker)

## Common Usage

### Initialization

To initialize the project with default settings:

```bash
./init.sh
```

This will:

1. Create necessary directories
2. Start all Docker services
3. Run database migrations
4. Create a default admin user (username: admin, password: admin)

To initialize with custom admin credentials:

```bash
./init.sh -u superadmin -p secret123
```

### Docker Service Management

```bash
# Start all services
./docker.sh start

# Stop all services
./docker.sh stop

# Restart all services
./docker.sh restart

# Restart a specific service
./docker.sh restart api

# Check status of all services
./docker.sh status

# View logs of all services
./docker.sh logs

# View logs of a specific service
./docker.sh logs api

# Follow logs of a specific service
./docker.sh logs api -f

# Update and rebuild services
./docker.sh update

# Pull latest images and clean build
./docker.sh update -p -c

# Clean up containers
./docker.sh clean -c

# Clean up containers and volumes
./docker.sh clean -v

# Clean up data directories
./docker.sh clean -d

# Clean up everything
./docker.sh clean -a
```

### Database Management

```bash
# Run database migrations
./database.sh migrate

# Show database status
./database.sh status

# Create a backup
./database.sh backup

# Create a backup in a specific directory
./database.sh backup -o /path/to/backups

# Restore a backup
./database.sh restore ./backups/videotranscriber_backup_20250511_123456.sql.gz

# Force restore without confirmation
./database.sh restore -f ./backups/videotranscriber_backup_20250511_123456.sql

# Fix database schema issues
./database.sh fix

# List users in the database
./database.sh users
```

### User Management

```bash
# Create a regular user
./user.sh create -u john -p secret123

# Create an admin user
./user.sh create -u admin -p admin123 -a

# Create a default admin user
./user.sh create-admin

# Create a custom admin user
./user.sh create-admin -u superadmin -p strongpass

# Force creation even if users exist
./user.sh create-admin -f

# List all users
./user.sh list
```

### Running Locally (Without Docker)

```bash
# Run the application locally
./local.sh
```

This will:

1. Check if PostgreSQL is running locally
2. Check if Ollama is running locally
3. Run database migrations
4. Start the application

## Getting Help

All scripts provide help information when run with the `-h` or `--help` flag:

```bash
./vt help
./vt init -h
./vt docker -h
./vt db -h
./vt user -h
./vt local -h
```

Or when run without any arguments:

```bash
./vt docker
./vt db
./vt user
```
