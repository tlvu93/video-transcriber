# PyProject.toml Modernization

This document explains the advantages of using `pyproject.toml` over traditional `requirements.txt` files and the modernization changes made to this project.

## Advantages of pyproject.toml over requirements.txt

### 1. **Standardized Project Metadata**

- Contains project name, version, description, license, and Python version requirements
- Single source of truth for project information
- Eliminates need for separate `setup.py` files

### 2. **Dependency Management with Categories**

- Organize dependencies into logical groups (dev, ml, audio, whisper, etc.)
- Install specific dependency sets: `pip install .[dev]` or `pip install .[all]`
- Better separation of concerns between production and development dependencies

### 3. **Tool Configuration Centralization**

- Configure tools like black, isort, mypy directly in pyproject.toml
- Eliminates need for separate config files (`.black`, `setup.cfg`, `mypy.ini`)
- Single file for all project configuration

### 4. **Build System Specification**

- Defines how packages should be built with `[build-system]` section
- More reproducible builds across different environments
- Better integration with modern Python packaging tools

### 5. **Better Dependency Resolution**

- Modern pip resolvers work better with pyproject.toml's richer dependency specification
- More precise version constraints and conflict resolution
- Support for extras and optional dependencies

## Changes Made

### Common Package

- **Before**: Used `setup.py` and `requirements.txt`
- **After**: Migrated to `pyproject.toml` with proper metadata and dependencies

### Service Dockerfiles

- **Before**: Multiple manual `pip install` commands with hardcoded versions
- **After**: Single `pip install -e .[extras]` command using pyproject.toml

### Dependency Organization

Each service now has well-organized dependencies:

#### Transcription Service

- **Base dependencies**: Core functionality (ffmpeg-python, numpy, requests, pika)
- **ML dependencies**: PyTorch components
- **Audio dependencies**: Audio processing libraries (librosa, soundfile, etc.)
- **Whisper dependencies**: Speech recognition libraries
- **All dependencies**: Convenience group that includes everything

#### API Service

- **Base dependencies**: FastAPI, database, and messaging components
- **Dev dependencies**: Testing and code quality tools

#### Summarization Service

- **Base dependencies**: NLP and messaging libraries
- **Dev dependencies**: Development tools

#### Watcher Service

- **Base dependencies**: File watching and HTTP client libraries
- **Dev dependencies**: Testing tools

## Benefits Achieved

1. **Simplified Dockerfiles**: Reduced from 15+ pip install commands to 3-4 commands
2. **Consistent Dependencies**: All dependencies defined in one place per service
3. **Better Maintainability**: Version updates only require changing pyproject.toml
4. **Improved Build Reliability**: Let pip handle dependency resolution instead of manual ordering
5. **Development Workflow**: Easy installation of dev tools with `pip install .[dev]`
6. **Modern Standards**: Aligned with current Python packaging best practices

## Local Development

To install a service with all dependencies:

```bash
cd services/transcription-service
pip install -e .[all]
```

To install only development dependencies:

```bash
pip install -e .[dev]
```

To install specific dependency groups:

```bash
pip install -e .[ml,audio]  # Only ML and audio dependencies
```

## Docker Benefits

The modernized Dockerfiles are:

- **Simpler**: Fewer RUN commands and manual dependency management
- **More reliable**: Pip handles dependency resolution
- **Easier to maintain**: Changes only require updating pyproject.toml
- **Consistent**: All services follow the same pattern
