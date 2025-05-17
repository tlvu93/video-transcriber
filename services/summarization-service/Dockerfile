FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Install Python dependencies
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install --no-cache-dir requests langchain langchain-core nltk pika==1.3.2
RUN pip install --no-cache-dir -r /app/common/requirements.txt
RUN pip install --no-cache-dir -e /app/common

# Copy the summarization service code
COPY services/summarization-service /app/summarization-service

# Fix the dependency path in pyproject.toml
RUN sed -i 's|file://../common|file:///app/common|g' /app/summarization-service/pyproject.toml

# Now install the summarization service
RUN pip install --no-cache-dir -e /app/summarization-service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/transcriptions /app/data/summaries

# Set working directory to summarization service
WORKDIR /app/summarization-service

# Run the summarization service
CMD ["python", "-m", "summarization.main"]
