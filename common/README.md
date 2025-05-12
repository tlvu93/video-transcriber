# Common Package

Shared code and utilities for the Video Transcriber application.

## Overview

This package contains shared code and utilities used by all services in the Video Transcriber application:

- Database models and connection management
- Authentication and authorization
- Job queue management
- Configuration settings
- Utility functions

## Installation

```bash
# Install the package in development mode
pip install -e .
```

## Usage

```python
# Import database models
from common.models import User, Video, Transcript, Summary

# Import database utilities
from common.database import init_db, get_db, get_db_session

# Import authentication utilities
from common.auth import authenticate_user, create_access_token, get_current_user

# Import job queue utilities
from common.job_queue import get_next_transcription_job, mark_job_completed

# Import configuration settings
from common.config import DATABASE_URL, VIDEO_DIR, TRANSCRIPT_DIR

# Import utility functions
from common.utils import get_file_hash, get_video_metadata
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black common
isort common

# Type checking
mypy common
```
