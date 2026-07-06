# Caching and Invalidation

Lanternfish transforms may enable a lookup cache to avoid recomputing
expensive enrichment calls.

## Cache backends

Two backends are built in: an in-process LRU (default, bounded by entry
count) and a shared memory-mapped cache for multi-worker deployments.
Configure with `cache.backend: lru | mmap`.

## Invalidation strategies

- **TTL**: every entry expires after `cache.ttl` seconds. Simple and
  predictable; use it when the upstream data changes on a known schedule.
- **Event-driven**: a control-topic message invalidates matching keys
  immediately. Lower staleness, but requires wiring the upstream system to
  publish change events.
- **Versioned keys**: embed a version stamp in the cache key so stale
  entries are simply never read again and age out of the LRU naturally.

## Metrics

Watch `cache_hit_ratio` and `cache_evictions_total`. A hit ratio below
0.8 with high evictions means the cache is undersized for the working set.
