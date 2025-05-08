#!/bin/sh
set -e

echo "$(date): Starting Ollama entrypoint script"

# Install curl if it's not available
if ! command -v curl > /dev/null; then
    echo "$(date): curl not found, installing..."
    
    # Try apt-get (Debian/Ubuntu)
    if command -v apt-get > /dev/null; then
        apt-get update && apt-get install -y curl
    # Try apk (Alpine)
    elif command -v apk > /dev/null; then
        apk add --no-cache curl
    # Try yum (CentOS/RHEL)
    elif command -v yum > /dev/null; then
        yum install -y curl
    else
        echo "$(date): ERROR - Could not install curl, package manager not found"
        exit 1
    fi
    
    # Verify curl was installed
    if ! command -v curl > /dev/null; then
        echo "$(date): ERROR - Failed to install curl"
        exit 1
    else
        echo "$(date): curl installed successfully"
    fi
fi

# Start Ollama server in the background
echo "$(date): Starting Ollama server..."
ollama serve &
SERVER_PID=$!

# Wait for the server to start
echo "$(date): Waiting for Ollama server to start..."
sleep 10

# Check if server is running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "$(date): ERROR - Ollama server is not responding. Waiting longer..."
    sleep 20
    if ! curl -s http://localhost:11434/api/tags > /dev/null; then
        echo "$(date): ERROR - Ollama server failed to start properly"
    else
        echo "$(date): Ollama server is now responding"
    fi
else
    echo "$(date): Ollama server is responding"
fi

# Pull the model
echo "$(date): Pulling deepseek-r1 model..."
ollama pull deepseek-r1

# Verify the model was pulled successfully
echo "$(date): Verifying model was pulled successfully..."
if ollama list | grep -q "deepseek-r1"; then
    echo "$(date): Model deepseek-r1 is available"
else
    echo "$(date): WARNING - Model deepseek-r1 may not be available"
    echo "$(date): Available models:"
    ollama list
fi

# Test the model with a simple prompt
echo "$(date): Testing model with a simple prompt..."
if ! curl -s -X POST http://localhost:11434/api/generate -d '{"model": "deepseek-r1", "prompt": "Say hello", "stream": false}' > /dev/null; then
    echo "$(date): WARNING - Model test failed"
else
    echo "$(date): Model test successful"
fi

# Wait for the server process to finish (which it won't unless killed)
echo "$(date): Ollama server is running with model deepseek-r1 available"
wait $SERVER_PID
