# Configuration Reference

Lanternfish reads configuration from `pipeline.yaml` in the working
directory, or from the path given with `--config`.

## Top-level keys

- `sources`: list of input connectors (file, socket, generator).
- `transforms`: ordered list of processing stages.
- `sinks`: list of output connectors (stdout, file, socket).
- `runtime.workers`: number of worker threads, defaults to the CPU count.
- `runtime.buffer_size`: per-stage ring buffer capacity in events.

## Environment variable interpolation

Any string value may reference environment variables using the
`${VAR_NAME}` syntax. Unset variables cause a validation error at startup
unless a default is provided: `${VAR_NAME:-fallback}`.

## Precedence

Command-line flags override environment variables, which override values
from the configuration file. Defaults apply last.
