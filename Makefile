# Makefile for Meshtastic Matrix Relay Docker operations

.PHONY: help build run stop logs shell clean config generate-compose

# Default target
help:
	@echo "Available targets:"
	@echo "  generate-compose - Generate docker-compose.yml from sample_config.yaml"
	@echo "  build           - Build the Docker image"
	@echo "  run             - Start the container with docker-compose"
	@echo "  stop            - Stop the container"
	@echo "  restart  - Restart the container"
	@echo "  logs            - Show container logs"
	@echo "  shell           - Access container shell"
	@echo "  clean           - Remove containers and images"
	@echo "  config          - Copy sample config file"
	@echo "  backup          - Backup container data"
	@echo "  restore         - Restore container data"

# Generate docker-compose.yml from sample config
generate-compose:
	python3 scripts/generate-docker-compose.py

# Build the Docker image
build:
	docker-compose build

# Start the container
run:
	docker-compose up -d

# Stop the container
stop:
	docker-compose down

# Restart the container
restart:
	docker-compose restart

# Show logs
logs:
	docker-compose logs -f

# Access container shell
shell:
	docker-compose exec mmrelay bash

# Clean up containers and images
clean:
	docker-compose down -v
	docker system prune -f

# Copy sample config
config:
	@if [ ! -f config.yaml ]; then \
		cp docker-config.yaml config.yaml; \
		echo "Sample config copied to config.yaml - please edit it before running"; \
	else \
		echo "config.yaml already exists"; \
	fi

# Backup data
backup:
	@echo "Creating backup..."
	docker run --rm -v mmrelay_data:/data -v $(PWD):/backup alpine tar czf /backup/mmrelay-data-backup-$(shell date +%Y%m%d-%H%M%S).tar.gz -C /data .
	@echo "Backup created: mmrelay-data-backup-$(shell date +%Y%m%d-%H%M%S).tar.gz"

# Restore data (requires BACKUP_FILE variable)
restore:
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Usage: make restore BACKUP_FILE=mmrelay-data-backup-YYYYMMDD-HHMMSS.tar.gz"; \
		exit 1; \
	fi
	@echo "Restoring from $(BACKUP_FILE)..."
	docker run --rm -v mmrelay_data:/data -v $(PWD):/backup alpine tar xzf /backup/$(BACKUP_FILE) -C /data
	@echo "Restore completed"

# Show status
status:
	docker-compose ps
