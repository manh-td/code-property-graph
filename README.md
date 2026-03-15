# Code Property Graph Playground (Joern)

This repository is a reproducible playground for generating and processing Code Property Graph (CPG) data with [Joern](https://github.com/joernio/joern), with side-by-side support for:

- `latest`
- `v1.1.1298`

It includes:

- Version-specific Joern runner scripts
- Scala scripts for import and graph export
- Python extractors that normalize Joern JSON and build line-level PDG artifacts
- A metrics workflow for the `latest` track
- Checked-in sample outputs for both Joern versions

## Repository Layout

- `bash-scripts/install-joern.sh`: installs Joern into `./joerns/latest` and `./joerns/v1.1.1298`
- `bash-scripts/latest/`: run latest Joern export, extractor, and metrics
- `bash-scripts/v1.1.1298/`: run v1.1.1298 Joern export and extractor
- `joern-scripts/latest/`: `import_code.scala`, `get_func_graph.scala`, `compute_metrics.scala`, `graph-for-funcs.scala`
- `joern-scripts/v1.1.1298/`: `import_code.scala`, `get_func_graph.scala`
- `src/latest/extractor.py`: normalization + PDG pipeline for latest export
- `src/v1_1_1298/extractor.py`: normalization + PDG pipeline for v1.1.1298 export
- `examples/`: sample Python inputs
- `joern-output/`: raw Joern JSON exports (`*.nodes.json`, `*.edges.json`, `*.metrics.json`)
- `cache/`: extractor stage-by-stage outputs (`01_*` through `06_*` + `summary.json`)
- `workspace/`: Joern project workspace artifacts

## Prerequisites

- Docker Engine
- Docker Compose
- `curl` (for `bash-scripts/install-joern.sh`)

## Quick Start

1. Install both Joern versions on the host:

```bash
bash bash-scripts/install-joern.sh
```

2. Build and start the container:

```bash
docker compose up -d --build
```

3. Open a shell in the container:

```bash
docker exec -it code-property-graph-container /bin/bash
```

4. Run one of the pipelines below.

## Latest Pipeline

Run Joern export:

```bash
bash bash-scripts/latest/joern.sh
```

Run Python extractor:

```bash
bash bash-scripts/latest/extractor.sh
```

Run repository metrics:

```bash
bash bash-scripts/latest/metrics.sh
```

## v1.1.1298 Pipeline

Run Joern export:

```bash
bash bash-scripts/v1.1.1298/joern.sh
```

Run Python extractor:

```bash
bash bash-scripts/v1.1.1298/extractor.sh
```

Expected outputs:

- `joern-output/v1.1.1298/examples.nodes.json`
- `joern-output/v1.1.1298/examples.edges.json`
- `cache/v1.1.1298/examples/01_raw_nodes.json`
- `cache/v1.1.1298/examples/01_raw_edges.json`
- `cache/v1.1.1298/examples/02_nodes_normalized.csv`
- `cache/v1.1.1298/examples/02_edges_normalized.csv`
- `cache/v1.1.1298/examples/03_nodes_enriched.csv`
- `cache/v1.1.1298/examples/04_edges_with_lines.csv`
- `cache/v1.1.1298/examples/05_statement_nodes.csv`
- `cache/v1.1.1298/examples/05_statement_edges.csv`
- `cache/v1.1.1298/examples/05_dependency_edges.csv`
- `cache/v1.1.1298/examples/06_pdg_nodes.csv`
- `cache/v1.1.1298/examples/06_pdg_edges.json`
- `cache/v1.1.1298/examples/summary.json`

## Optional: Run Joern In Server Mode

Inside an environment where `joern` is on `PATH`:

```bash
bash bash-scripts/host-joern-server.sh
```

This starts Joern on `0.0.0.0:16240`.
