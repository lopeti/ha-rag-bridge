# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-07-31 | Migration from JavaScript-based ArangoDB operations to pure Python client | Eliminates dependency on arangosh binary and provides better integration with Python codebase. Improves deployment and reduces external dependencies. |
| 2025-07-31 | Rename _meta collection to meta with auto-migration | Breaking change to follow better naming conventions and avoid underscore prefixes. Auto-migration ensures smooth transition for existing installations. |
| 2025-07-31 | Upgrade minimum requirements to ArangoDB 3.11+ and python-arango 8.x | Required for vector index support and modern API features. Ensures stability and access to latest database capabilities. |
