# Code Property Graph Playground (Joern)

This repository is a reproducible playground for generating and exporting Code Property Graph (CPG) data with [Joern](https://github.com/joernio/joern), focused on Python examples and version comparison.

It includes:
- Two Joern tracks: `latest` and `v1.1.1298`
- Scala scripts for import and graph export
- Bash helpers to install and run workflows
- Example Python code and checked-in sample outputs

## Repository Layout

Key directories:
- `bash-scripts/`: install and test helpers
- `examples/`: sample Python inputs
- `joern-scripts/latest/`: scripts for recent Joern
- `joern-scripts/v1.1.1298/`: scripts for Joern `v1.1.1298`
- `joerns/`: local Joern installations (created by installer script)
- `joern-output/`: exported JSON node/edge output
- `workspace/`: Joern workspace artifacts created during imports

## Prerequisites

Choose one approach:

### Docker (recommended)
- Docker Engine
- Docker Compose

## Quick Start (Docker)

Outside the container, install Joern versions:

```bash
bash bash-scripts/install-joern.sh
```

Build and start the container:

```bash
docker compose up -d --build
```

Open a shell in the container:

```bash
docker exec -it code-property-graph-container /bin/bash
```

Run the latest pipeline:

```bash
bash bash-scripts/test.latest.sh
```

Run the `v1.1.1298` pipeline:

```bash
bash bash-scripts/test.v1.1.1298.sh
```

## What The Test Scripts Do

### `bash-scripts/test.latest.sh`

1. Creates output directories under `joern-output/`
2. Imports `examples/` into Joern workspace `sample-latest`
3. Runs `run.ossdataflow`
4. Exports:
	- `joern-output/latest/sample.nodes.json`
	- `joern-output/latest/sample.edges.json`

### `bash-scripts/test.v1.1.1298.sh`

1. Creates output directories under `joern-output/`
2. Imports `./examples` directory into workspace `sample-v1.1.1298`
3. Runs `run.ossdataflow`
4. Exports:
	- `joern-output/v1.1.1298/sample.nodes.json`
	- `joern-output/v1.1.1298/sample.edges.json`

## Running Joern Server (Optional)

Start Joern in server mode:

```bash
bash bash-scripts/host-joern.sh
```

This starts Joern on `0.0.0.0:16240`.