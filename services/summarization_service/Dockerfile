FROM python:3.12.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Copy the summarization service code
COPY services/summarization_service /app/summarization_service

RUN pip install --no-cache-dir -r /app/common/requirements.lock
RUN pip install --no-cache-dir -r /app/summarization_service/requirements.lock
RUN pip install --no-cache-dir --no-deps -e /app/common
RUN pip install --no-cache-dir --no-deps -e /app/summarization_service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/transcriptions /app/data/summaries

# Set working directory to summarization service
WORKDIR /app/summarization_service

# Run the summarization service
CMD ["python", "-m", "summarization.main"]
