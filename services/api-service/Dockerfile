FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Copy API service
COPY services/api-service /app/api-service

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Install common package first
RUN pip install --no-cache-dir -e /app/common

# Fix the dependency path in pyproject.toml to point to the correct location in container
RUN sed -i 's|file://../common|file:///app/common|g' /app/api-service/pyproject.toml

# Install the API service with all dependencies from pyproject.toml
RUN pip install --no-cache-dir -e /app/api-service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to API service
WORKDIR /app/api-service

# Run the API service
CMD ["python", "-m", "api.main"]
