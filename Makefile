# Auth-Helper API - Makefile
.PHONY: help build start stop restart logs test clean dev docker-build docker-run docker-stop docker-logs docker-test

# Default target
help: ## Show this help message
	@echo "Auth-Helper API - Available Commands"
	@echo "===================================="
	@awk 'BEGIN {FS = ":.*##"}; /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# Development commands
dev: ## Start development server (local Python)
	./run.sh

test: ## Run all tests
	source venv/bin/activate && python -m pytest tests/ -v

test-e2e: ## Run only e2e tests
	source venv/bin/activate && python -m pytest tests/test_e2e_workflows.py -v

test-coverage: ## Run tests with coverage report
	source venv/bin/activate && python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

lint: ## Run code linting
	source venv/bin/activate && python -m flake8 src/ tests/

format: ## Format code with black
	source venv/bin/activate && python -m black src/ tests/

install: ## Install development dependencies
	python -m venv venv
	source venv/bin/activate && pip install -r requirements.txt
	source venv/bin/activate && pip install pytest-cov black flake8

# Docker commands
build: ## Build Docker image
	docker build -t auth-helper:latest .

start: build ## Build and start containers
	docker-compose up -d

stop: ## Stop containers
	docker-compose down

restart: ## Restart containers
	docker-compose restart

logs: ## Show container logs
	docker-compose logs -f

status: ## Show container status
	docker-compose ps

# Production commands with nginx
start-prod: ## Start with nginx reverse proxy
	docker-compose --profile production up -d

stop-prod: ## Stop production setup
	docker-compose --profile production down

# Docker development commands  
docker-build: ## Build Docker image only
	docker build -t auth-helper:latest .

docker-run: docker-build ## Run single container (development)
	docker run -d --name auth-helper-dev \
		-p 8000:8000 \
		-v auth_helper_dev_data:/app/data \
		auth-helper:latest

docker-stop: ## Stop single development container
	docker stop auth-helper-dev && docker rm auth-helper-dev

docker-logs: ## Show logs from development container
	docker logs -f auth-helper-dev

docker-shell: ## Open shell in running container
	docker exec -it auth-helper-dev /bin/bash

docker-test: ## Run tests inside container
	docker run --rm -v $(PWD):/app -w /app auth-helper:latest \
		python -m pytest tests/ -v

# Utility commands
clean: ## Clean up containers, images, and volumes
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean everything including images
	docker-compose down -v
	docker system prune -af
	docker volume prune -f

backup-db: ## Backup database from container
	docker run --rm \
		-v auth_helper_data:/data \
		-v $(PWD):/backup \
		alpine cp /data/auth_helper.db /backup/auth_helper_backup_$(shell date +%Y%m%d_%H%M%S).db

restore-db: ## Restore database to container (usage: make restore-db DB=backup_file.db)
	@if [ -z "$(DB)" ]; then echo "Usage: make restore-db DB=backup_file.db"; exit 1; fi
	docker run --rm \
		-v auth_helper_data:/data \
		-v $(PWD):/backup \
		alpine cp /backup/$(DB) /data/auth_helper.db

# API testing commands
api-test: ## Test API endpoints (requires running service)
	@echo "Testing health endpoint..."
	@curl -f http://localhost:8000/health || echo "Health check failed"
	@echo "\nTesting key generation..."
	@curl -s -X POST http://localhost:8000/keys/generate \
		-H "Content-Type: application/json" \
		-d '{"name":"test-key","issuer":"Makefile","type":"totp"}' | jq .

api-docs: ## Open API documentation
	@echo "API docs available at: http://localhost:8000/docs"
	@command -v open >/dev/null 2>&1 && open http://localhost:8000/docs || echo "Open http://localhost:8000/docs in your browser"

# Monitoring commands
monitor: ## Monitor container resources
	docker stats auth-helper-auth-helper-1

health: ## Check service health
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health && echo " ✅ Service healthy" || echo " ❌ Service unhealthy"

# Development setup
setup: install ## Complete development setup
	@echo "Development environment setup complete!"
	@echo "Run 'make dev' to start development server"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make start' to start with Docker"

# Release commands
tag: ## Tag current version (usage: make tag VERSION=1.0.0)
	@if [ -z "$(VERSION)" ]; then echo "Usage: make tag VERSION=1.0.0"; exit 1; fi
	git tag -a v$(VERSION) -m "Release version $(VERSION)"
	git push origin v$(VERSION)

release: test docker-build ## Build release image
	@echo "Release image built: auth-helper:latest"
	@echo "Tag with: docker tag auth-helper:latest auth-helper:$(VERSION)"