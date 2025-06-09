# Dynamic Video Directory Mounting

This project supports automatically mounting multiple video directories from your host machine into Docker containers based on environment variable configuration.

## How It Works

The system uses a setup script (`setup-volumes.sh`) that reads your `.env` file and generates a `docker-compose.override.yml` file with the appropriate volume mounts.

## Configuration

### 1. Configure Video Directories

Edit your `.env` file to specify the container paths where videos should be accessible:

```bash
# Container paths (comma-separated)
VIDEO_DIRS=/app/data/videos,/app/custom_videos,/app/external_videos
```

### 2. Configure Host Directories (Optional)

Specify the corresponding host directories to mount:

```bash
# Host paths (comma-separated, corresponds to VIDEO_DIRS order)
HOST_VIDEO_PATHS=/home/user/videos,/media/external/movies,/data/recordings
```

If `HOST_VIDEO_PATHS` is empty or not set, the system will use `./data/videos` as the default host path for custom directories.

## Usage

### 1. Run the Setup Script

Before starting Docker Compose, run the setup script to generate volume mounts:

```bash
./setup-volumes.sh
```

This will:

- Read your `.env` configuration
- Generate `docker-compose.override.yml` with appropriate volume mounts
- Show you what directories will be mounted

### 2. Start Docker Compose

```bash
docker-compose up
```

Docker Compose will automatically use both `docker-compose.yml` and `docker-compose.override.yml`.

## Example Configurations

### Basic Setup (Default)

```bash
# .env
VIDEO_DIRS=/app/data/videos,/app/custom_videos
HOST_VIDEO_PATHS=
```

Result:

- `./data/videos` → `/app/data/videos` (via standard mount)
- `./data/videos` → `/app/custom_videos` (default fallback)

### Multiple Custom Directories

```bash
# .env
VIDEO_DIRS=/app/data/videos,/app/movies,/app/recordings
HOST_VIDEO_PATHS=/home/user/videos,/media/movies,/backup/recordings
```

Result:

- `./data/videos` → `/app/data/videos` (via standard mount)
- `/home/user/videos` → `/app/movies`
- `/media/movies` → `/app/recordings`

### Mixed Setup

```bash
# .env
VIDEO_DIRS=/app/data/videos,/app/custom_videos,/app/external
HOST_VIDEO_PATHS=,/media/external
```

Result:

- `./data/videos` → `/app/data/videos` (via standard mount)
- `./data/videos` → `/app/custom_videos` (default fallback)
- `/media/external` → `/app/external`

## Important Notes

1. **Host Directory Requirements**: Make sure all host directories exist and contain your video files before running Docker Compose.

2. **Automatic Generation**: The `docker-compose.override.yml` file is auto-generated. Don't edit it manually as changes will be overwritten.

3. **Git Ignore**: Consider adding `docker-compose.override.yml` to your `.gitignore` if it contains machine-specific paths.

4. **Services Affected**: The following services will have the video directories mounted:

   - `api`
   - `transcription-worker`
   - `watcher`

5. **Re-run Setup**: If you change your `.env` configuration, re-run `./setup-volumes.sh` before restarting Docker Compose.

## Troubleshooting

### Permission Issues

If you encounter permission issues, ensure your host directories are readable by the Docker containers:

```bash
chmod -R 755 /path/to/your/videos
```

### Path Not Found

If Docker complains about paths not existing:

1. Verify the host paths exist: `ls -la /your/host/path`
2. Check your `.env` configuration
3. Re-run `./setup-volumes.sh`

### Override File Issues

If you need to reset the override file:

```bash
rm docker-compose.override.yml
./setup-volumes.sh
```
