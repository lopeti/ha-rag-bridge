.PHONY: migrate
migrate:
	arangosh --server.endpoint $$ARANGO_URL \
			 --server.username $$ARANGO_USER \
			 --server.password $$ARANGO_PASS \
			 --javascript.execute migrations/001_init_collections.arangodb

.PHONY: docs
docs: docs/architecture.svg

COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: dev-up dev-down dev-shell

dev-up:
	$(COMPOSE_DEV) up -d

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
