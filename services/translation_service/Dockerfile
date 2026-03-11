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

# Copy the translation service code
COPY services/translation_service /app/translation_service

RUN pip install --no-cache-dir -r /app/common/requirements.lock
RUN pip install --no-cache-dir -r /app/translation_service/requirements.lock
RUN pip install --no-cache-dir --no-deps -e /app/common
RUN pip install --no-cache-dir --no-deps -e /app/translation_service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/translations

# Set working directory to translation service
WORKDIR /app/translation_service

# Run the translation service
CMD ["python", "-m", "translation.main"]
