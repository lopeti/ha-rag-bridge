.PHONY: migrate
migrate:
	arangosh --server.endpoint $$ARANGO_URL \
			 --server.username $$ARANGO_USER \
			 --server.password $$ARANGO_PASS \
			 --javascript.execute migrations/001_init_collections.arangodb

.PHONY: docs
docs: docs/architecture.svg

COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev

.PHONY: dev-up dev-up-with-ui dev-down dev-shell

dev-up:
	$(COMPOSE_DEV) up -d

dev-up-with-ui:
	$(COMPOSE_DEV) up -d --build

dev-down:
	$(COMPOSE_DEV) down

dev-shell:
	$(COMPOSE_DEV) exec bridge bash

# Smart Deploy parancsok - GYORS TELEPÍTÉS
.PHONY: deploy deploy-to deploy-start deploy-check deploy-host host-deploy

# Devcontainer deploy (csak devcontainer-en belül látható)
deploy:
	./quick-deploy.sh

deploy-to:
	./quick-deploy.sh $(TARGET)

deploy-start: deploy
	cd ~/ha-rag-core && ./start.sh

deploy-check:
	@if [ -d ~/ha-rag-core ]; then cd ~/ha-rag-core && ./status.sh; else echo "❌ Nincs deploy-olt verzió"; fi

# Host deploy (Portainer-ben látható)
deploy-host:
	@echo "⚠️  Run this OUTSIDE devcontainer for Portainer visibility!"
	./host-deploy.sh

host-deploy:
	./host-docker-deploy.sh

# Monitoring Stack
.PHONY: monitoring-up monitoring-down monitoring-logs

monitoring-up:
	docker compose -f docker-compose.monitoring.yml up -d

monitoring-down:
	docker compose -f docker-compose.monitoring.yml down

monitoring-logs:
	docker compose -f docker-compose.monitoring.yml logs -f

# Docker Cleanup & Maintenance
.PHONY: docker-cleanup docker-prune docker-clean-dev docker-system-info

docker-cleanup:
	@echo "🧹 Cleaning unused Docker resources..."
	docker image prune -f
	docker container prune -f
	docker network prune -f
	docker volume prune -f

docker-prune:
	@echo "🧹 Deep cleaning ALL unused Docker resources (including BuildKit cache)..."
	docker system prune -a -f --volumes
	docker builder prune -f

docker-clean-dev:
	@echo "🧹 Cleaning development-specific Docker resources..."
	@echo "Removing <none> images..."
	-docker images --filter "dangling=true" --format "{{.ID}}" | xargs -r docker rmi -f
	@echo "Note: Active ha-rag-bridge images not removed (in use by running containers)"

docker-system-info:
	@echo "💾 Docker disk usage:"
	docker system df
	@echo ""
	@echo "🖼️  Images count:"
	docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | head -20

# UI Development Commands
.PHONY: ui-deps ui-dev ui-build ui-up ui-down ui-logs

ui-deps: ## Install frontend dependencies
	cd frontend && npm install

ui-dev: ## Start UI development server  
	cd frontend && npm start

ui-build: ## Build UI for production
	cd frontend && npm run build

ui-up: ## Start full stack with UI
	docker-compose -f docker-compose.ui.yml up -d

ui-down: ## Stop UI stack
	docker-compose -f docker-compose.ui.yml down

ui-logs: ## View UI logs
	docker-compose -f docker-compose.ui.yml logs -f ha-rag-ui
