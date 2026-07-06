# Changelog

## 2.4.0

- New `mmap` cache backend for multi-worker deployments.
- OAuth 2.0 device flow for CLI login.
- Breaking: `runtime.threads` renamed to `runtime.workers`.

## 2.3.1

- Fix: generator source ignored the configured rate limit after a
  hot-reload.
- Fix: readiness probe returned 200 during state migration.

## 2.3.0

- Windowed aggregations can now spill to disk (`window.spill: true`).
- Structured JSON logging is the default; the plaintext format was
  removed.

## 2.2.0

- Kubernetes lease-based partition ownership for horizontally scaled
  sources.
- Static API tokens with read-only scope.
