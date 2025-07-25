.PHONY: migrate
migrate:
	arangosh --server.endpoint $$ARANGO_URL \
	         --server.username $$ARANGO_USER \
	         --server.password $$ARANGO_PASS \
	         --javascript.execute migrations/001_init_collections.arangodb

.PHONY: docs
docs: docs/architecture.svg


COMPOSE_DEV = docker-compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: dev-up dev-down dev-shell

dev-up:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-shell:
	$(COMPOSE_DEV) exec bridge bash
