.PHONY: setup up down clean help benchmark-models compile-locks smoke smoke-e2e

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup    - Generate docker-compose.override.yml from .env configuration"
	@echo "  make up       - Run setup and start Docker Compose services"
	@echo "  make down     - Stop Docker Compose services"
	@echo "  make clean    - Remove generated docker-compose.override.yml"
	@echo "  make smoke    - Build the stack and verify frontend plus services are reachable"
	@echo "  make smoke-e2e - Run the full upload-to-processing smoke test"
	@echo "  make benchmark-models - Compare Ollama models against the latest transcript"
	@echo "  make compile-locks - Regenerate service lock files from the root pyproject extras"
	@echo "  make help     - Show this help message"

# Generate docker-compose.override.yml from .env configuration
setup:
	@echo "Setting up dynamic video directory mounts..."
	./scripts/setup-volumes.sh

# Run setup and start services
up: setup
	@echo "Starting Docker Compose services..."
	docker compose up

# Stop services
down:
	@echo "Stopping Docker Compose services..."
	docker compose down

# Build and smoke-test the running stack
smoke:
	@./scripts/smoke-compose.sh

# Run the full upload-to-processing smoke flow
smoke-e2e:
	@./scripts/smoke-e2e-compose.sh

# Clean generated files
clean:
	@echo "Removing generated docker-compose.override.yml..."
	@rm -f docker-compose.override.yml
	@echo "Clean complete."

# Compare configured Ollama models using the latest transcript from the local API
benchmark-models:
	@python3 ./scripts/benchmark_ollama_models.py --latest-transcript

# Regenerate service-specific lock files from the canonical backend manifest
compile-locks:
	@./scripts/compile-service-locks.sh
