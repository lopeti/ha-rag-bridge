# Changelog

## Unreleased

- Added validation of collection names during bootstrap.
- New CLI flags `--skip-invalid` and `--rename-invalid` to handle illegal names.
- Breaking change: `_meta` collection renamed to `meta` and auto-migrated.
- Breaking internal: JS-API calls replaced with Python client; no arangosh binary needed in v12.5.
- feat: tini PID-1 init wrapper; graceful shutdown in Docker.
- Persistent index creation rewritten with python-arango API; no JavaScript fallback calls remain.

## v12.6

- Arango REST index calls now resilient w/ exp-backoff.
- CLI returns proper codes.

