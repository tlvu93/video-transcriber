#!/bin/sh
set -e

# Start Ollama server in the background
ollama serve &
SERVER_PID=$!

# Wait for the server to start
echo "Waiting for Ollama server to start..."
sleep 10

# Pull the model
echo "Pulling deepseek-r1 model..."
ollama pull deepseek-r1

# Wait for the server process to finish (which it won't unless killed)
echo "Ollama server is running with model deepseek-r1 available"
wait $SERVER_PID
