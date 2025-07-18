.PHONY: migrate
migrate:
	arangosh --server.endpoint $$ARANGO_URL \
	         --server.username $$ARANGO_USER \
	         --server.password $$ARANGO_PASS \
	         --javascript.execute migrations/001_init_collections.arangodb

.PHONY: docs
docs: docs/architecture.svg

