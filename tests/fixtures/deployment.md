# Deployment Guide

This guide covers running Lanternfish in containers and on Kubernetes.

## Docker

The official image is distroless and runs as a non-root user. Mount your
pipeline definition and expose the metrics port:

```bash
docker run -v ./pipeline.yaml:/etc/lanternfish/pipeline.yaml:ro \
  -p 9600:9600 lanternfish:2.4.0
```

## Kubernetes

Deploy as a StatefulSet when your transforms keep local state (windowed
aggregations), otherwise a plain Deployment is fine. A readiness probe on
`/healthz` and a liveness probe on `/livez` are exposed on the metrics
port. Horizontal scaling is safe for stateless pipelines because sources
coordinate partition ownership through a lease table.

## Resource sizing

Start with one CPU and 512 MiB per 10k events/second and adjust using the
`stage_backpressure_seconds` metric. Sustained backpressure above 0.5s
means the pipeline needs more workers or a larger buffer.
