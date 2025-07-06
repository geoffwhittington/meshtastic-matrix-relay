# Makefile for Meshtastic Matrix Relay Docker operations

.PHONY: help build run stop logs shell clean config

# Default target
help:
	@echo "Available Docker commands:"
	@echo "  config  - Copy sample config file"
	@echo "  build   - Build the Docker image"
	@echo "  run     - Start the container"
	@echo "  stop    - Stop the container"
	@echo "  logs    - Show container logs"
	@echo "  shell   - Access container shell"
	@echo "  clean   - Remove containers and volumes"

# Copy sample config
config:
	@if [ ! -f config.yaml ]; then \
		cp src/mmrelay/tools/sample_config.yaml config.yaml; \
		echo "Sample config copied to config.yaml - please edit it before running"; \
	else \
		echo "config.yaml already exists"; \
	fi

# Build the Docker image
build:
	docker-compose build

# Start the container
run:
	docker-compose up -d

# Stop the container
stop:
	docker-compose down

# Show logs
logs:
	docker-compose logs -f

# Access container shell
shell:
	docker-compose exec mmrelay bash

# Clean up containers and volumes
clean:
	docker-compose down -v
