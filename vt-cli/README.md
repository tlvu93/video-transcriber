# Video Transcriber CLI

This directory contains the Video Transcriber CLI (Command Line Interface) tools for managing the Video Transcriber application.

## Usage

You can run the CLI from the root directory using the `vt` command:

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

## CLI Structure

The CLI is organized into a modular structure:

- `vt.sh`: Main command interface
- `utils.sh`: Common utility functions used by other scripts
- `docker.sh`: Docker service management
- `database.sh`: Database management
- `user.sh`: User management
- `init.sh`: Project initialization
- `local.sh`: Run the application locally (without Docker)

## Documentation

- `README.md`: This file
- `README-SCRIPTS.md`: Quick start guide
- `SCRIPTS.md`: Detailed documentation on all available commands and options

## Getting Help

All scripts provide help information when run with the `-h` or `--help` flag:

```bash
./vt help
./vt docker -h
./vt db -h
```
