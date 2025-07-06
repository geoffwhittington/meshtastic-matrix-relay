# Makefile for Meshtastic Matrix Relay Docker operations

.PHONY: help build run stop logs shell clean config edit setup

# Default target
help:
	@echo "Available Docker commands:"
	@echo "  setup   - Copy sample config and open editor (recommended for first time)"
	@echo "  config  - Copy sample config to ~/.mmrelay/config.yaml"
	@echo "  edit    - Edit the config file with your preferred editor"
	@echo "  build   - Build the Docker image"
	@echo "  run     - Start the container"
	@echo "  stop    - Stop the container"
	@echo "  logs    - Show container logs"
	@echo "  shell   - Access container shell"
	@echo "  clean   - Remove containers"

# Copy sample config to ~/.mmrelay/config.yaml
config:
	@mkdir -p ~/.mmrelay
	@if [ ! -f ~/.mmrelay/config.yaml ]; then \
		cp src/mmrelay/tools/sample_config.yaml ~/.mmrelay/config.yaml; \
		echo "Sample config copied to ~/.mmrelay/config.yaml - please edit it before running"; \
	else \
		echo "~/.mmrelay/config.yaml already exists"; \
	fi

# Edit the config file with preferred editor
edit:
	@if [ ! -f ~/.mmrelay/config.yaml ]; then \
		echo "Config file not found. Run 'make config' first."; \
		exit 1; \
	fi
	@if [ -n "$$EDITOR" ]; then \
		$$EDITOR ~/.mmrelay/config.yaml; \
	else \
		echo "Select your editor:"; \
		echo "1) nano (beginner-friendly)"; \
		echo "2) vim"; \
		echo "3) emacs"; \
		echo "4) code (VS Code)"; \
		echo "5) gedit"; \
		read -p "Enter choice (1-5): " choice; \
		case $$choice in \
			1) nano ~/.mmrelay/config.yaml ;; \
			2) vim ~/.mmrelay/config.yaml ;; \
			3) emacs ~/.mmrelay/config.yaml ;; \
			4) code ~/.mmrelay/config.yaml ;; \
			5) gedit ~/.mmrelay/config.yaml ;; \
			*) echo "Invalid choice. Set EDITOR environment variable or try again."; exit 1 ;; \
		esac \
	fi

# Setup: copy config and open editor (recommended for first time)
setup:
	@$(MAKE) config
	@$(MAKE) edit

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

# Clean up containers (data in ~/.mmrelay/ is preserved)
clean:
	docker-compose down
