.PHONY: setup up down clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup    - Generate docker-compose.override.yml from .env configuration"
	@echo "  make up       - Run setup and start Docker Compose services"
	@echo "  make down     - Stop Docker Compose services"
	@echo "  make clean    - Remove generated docker-compose.override.yml"
	@echo "  make help     - Show this help message"

# Generate docker-compose.override.yml from .env configuration
setup:
	@echo "Setting up dynamic video directory mounts..."
	./setup-volumes.sh

# Run setup and start services
up: setup
	@echo "Starting Docker Compose services..."
	docker-compose up

# Stop services
down:
	@echo "Stopping Docker Compose services..."
	docker-compose down

# Clean generated files
clean:
	@echo "Removing generated docker-compose.override.yml..."
	@rm -f docker-compose.override.yml
	@echo "Clean complete."
