# Video Transcriber Scripts

This project includes a set of shell scripts to manage the Video Transcriber application. The scripts have been organized into a modular structure to make them easier to maintain and use.

## Quick Start

The easiest way to use the scripts is through the unified command interface:

```bash
# Initialize the project
./vt init

# Start Docker services
./vt docker start

# Check status
./vt docker status

# Create an admin user
./vt user create-admin

# Run database migrations
./vt db migrate

# View logs
./vt docker logs
```

## Script Structure

The scripts have been organized into a modular structure:

- `vt`: Main command interface (symlink to vt.sh)
- `utils.sh`: Common utility functions used by other scripts
- `docker.sh`: Docker service management
- `database.sh`: Database management
- `user.sh`: User management
- `init.sh`: Project initialization

## Detailed Documentation

For detailed documentation on all available commands and options, see [SCRIPTS.md](SCRIPTS.md).

## Getting Help

All scripts provide help information when run with the `-h` or `--help` flag:

```bash
./vt help
./vt docker -h
./vt db -h
```

## Common Tasks

### Initialize the Project

```bash
# Initialize with default settings
./vt init

# Initialize with custom admin credentials
./vt init -u superadmin -p secret123
```

### Manage Docker Services

```bash
# Start all services
./vt docker start

# Stop all services
./vt docker stop

# Restart a specific service
./vt docker restart api

# Check status
./vt docker status

# View logs
./vt docker logs

# View logs of a specific service
./vt docker logs api
```

### Manage Database

```bash
# Run migrations
./vt db migrate

# Show database status
./vt db status

# Create a backup
./vt db backup

# Restore a backup
./vt db restore ./backups/videotranscriber_backup_20250511_123456.sql.gz
```

### Manage Users

```bash
# Create a regular user
./vt user create -u john -p secret123

# Create an admin user
./vt user create -u admin -p admin123 -a

# List all users
./vt user list
```
