# Getting Started with Lanternfish

Lanternfish is a fictional stream-processing toolkit used here as test
corpus content. It ships as a single static binary with no external
dependencies.

## Installation

Download the release archive for your platform and unpack it somewhere on
your PATH:

```bash
tar -xzf lanternfish-2.4.0-linux-amd64.tar.gz
sudo mv lanternfish /usr/local/bin/
```

Verify the installation with `lanternfish --version`.

## Your first pipeline

Create a file called `pipeline.yaml` with a source, a transform, and a sink.
Then run `lanternfish run pipeline.yaml`. The engine watches the file and
hot-reloads on change, so you can iterate without restarting.
