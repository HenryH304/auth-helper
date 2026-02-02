.PHONY: build run stop logs shell test test-local clean dev venv

-include .env

IMAGE_NAME = auth-helper
CONTAINER_NAME = auth-helper
PORT ?= 8000
VENV_DIR = .venv
export PORT

# Detect zbar library path for macOS
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    export DYLD_LIBRARY_PATH := /opt/homebrew/lib
endif

# Build the Docker image
build:
	docker build -t $(IMAGE_NAME) .

# Run the container
run:
	docker run -d --name $(CONTAINER_NAME) -p $(PORT):8000 -v $(PWD)/data:/app/data $(IMAGE_NAME)

# Stop and remove the container
stop:
	docker stop $(CONTAINER_NAME) 2>/dev/null || true
	docker rm $(CONTAINER_NAME) 2>/dev/null || true

# View container logs
logs:
	docker logs -f $(CONTAINER_NAME)

# Open a shell in the running container
shell:
	docker exec -it $(CONTAINER_NAME) /bin/bash

# Run tests inside container
test:
	docker run --rm -v $(PWD)/tests:/app/tests $(IMAGE_NAME) pytest tests/ -v

# Run tests locally using venv
test-local:
	$(VENV_DIR)/bin/python -m pytest tests/ -v

# Create virtual environment and install dependencies
venv:
	python3 -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt

# Remove image and container
clean: stop
	docker rmi $(IMAGE_NAME) 2>/dev/null || true

# Rebuild and run
dev: stop build run logs
