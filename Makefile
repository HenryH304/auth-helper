.PHONY: build run stop logs shell test clean dev

-include .env

IMAGE_NAME = auth-helper
CONTAINER_NAME = auth-helper
PORT ?= 8000
export PORT

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

# Remove image and container
clean: stop
	docker rmi $(IMAGE_NAME) 2>/dev/null || true

# Rebuild and run
dev: stop build run logs
