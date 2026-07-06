# Troubleshooting

Common failure modes and how to diagnose them.

## Pipeline stalls with no error

Usually a sink applying backpressure. Check the
`stage_backpressure_seconds` metric per stage; the first stage showing
sustained pressure is downstream of the bottleneck. Socket sinks stall
when the remote peer stops reading.

## "checksum mismatch" on startup

The state directory was written by a different Lanternfish version.
Run `lanternfish state migrate` to upgrade in place, or delete the state
directory to rebuild from the source offsets.

## High memory usage

Windowed aggregations hold every open window in memory. Reduce
`window.max_open` or enable spill-to-disk with `window.spill: true`.
Generator sources with `rate: unlimited` can also flood the ring buffers;
set an explicit rate during testing.

## Logs

Structured logs go to stderr as JSON. Set `LANTERNFISH_LOG=debug` for
per-event tracing (very verbose; do not use in production).
