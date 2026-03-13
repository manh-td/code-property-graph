#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


def unwrap(value: Any) -> Any:
	"""Unwrap Joern GraphSON typed values into plain Python values."""
	if isinstance(value, dict):
		if "@value" in value:
			return unwrap(value["@value"])
		return {k: unwrap(v) for k, v in value.items()}
	if isinstance(value, list):
		return [unwrap(v) for v in value]
	return value


def first_prop(props: dict[str, Any], key: str, default: str = "") -> str:
	raw = props.get(key)
	if not raw:
		return default
	v = unwrap(raw)
	if isinstance(v, dict) and "@value" in v:
		v = unwrap(v["@value"])
	if isinstance(v, list) and v:
		return str(v[0])
	return str(v) if v is not None else default


def discover_export_files(input_path: Path) -> list[Path]:
	if input_path.is_file():
		return [input_path]
	return sorted(input_path.rglob("export.json"))


def node_color(label: str) -> str:
	palette = [
		"#1f77b4",
		"#ff7f0e",
		"#2ca02c",
		"#d62728",
		"#9467bd",
		"#8c564b",
		"#e377c2",
		"#7f7f7f",
		"#bcbd22",
		"#17becf",
	]
	return palette[sum(ord(c) for c in label) % len(palette)]


def build_graph(export_files: list[Path], max_nodes: int, edge_types: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	nodes_by_id: dict[str, dict[str, Any]] = {}
	edges: list[dict[str, Any]] = []

	for file_path in export_files:
		data = json.loads(file_path.read_text(encoding="utf-8"))
		graph = data.get("@value", {})
		vertices = graph.get("vertices", [])
		raw_edges = graph.get("edges", [])

		for vertex in vertices:
			vid = str(unwrap(vertex.get("id")))
			if not vid:
				continue

			label = vertex.get("label", "NODE")
			props = vertex.get("properties", {})
			code = first_prop(props, "CODE")
			name = first_prop(props, "NAME")
			full_name = first_prop(props, "FULL_NAME")
			filename = first_prop(props, "FILENAME")

			title_parts = [
				f"type: {label}",
				f"id: {vid}",
			]
			if name:
				title_parts.append(f"name: {name}")
			if full_name:
				title_parts.append(f"full_name: {full_name}")
			if filename:
				title_parts.append(f"file: {filename}")
			if code:
				title_parts.append(f"code: {code}")

			shown = name or full_name or (code[:40] + "..." if len(code) > 40 else code) or vid
			nodes_by_id[vid] = {
				"id": vid,
				"label": f"{label}\\n{shown}",
				"title": "\\n".join(title_parts),
				"group": label,
				"color": node_color(label),
			}

		for edge in raw_edges:
			edge_label = edge.get("label", "")
			if edge_types and edge_label not in edge_types:
				continue

			source = str(unwrap(edge.get("outV")))
			target = str(unwrap(edge.get("inV")))
			if not source or not target:
				continue

			edges.append(
				{
					"from": source,
					"to": target,
					"label": edge_label,
					"arrows": "to",
				}
			)

	nodes = list(nodes_by_id.values())
	if max_nodes > 0 and len(nodes) > max_nodes:
		keep = {n["id"] for n in nodes[:max_nodes]}
		nodes = [n for n in nodes if n["id"] in keep]
		edges = [e for e in edges if e["from"] in keep and e["to"] in keep]
	else:
		existing = {n["id"] for n in nodes}
		edges = [e for e in edges if e["from"] in existing and e["to"] in existing]

	return nodes, edges


def write_html(output_path: Path, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Joern CPG Visualization</title>
  <script src=\"https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js\"></script>
  <style>
	body {{ margin: 0; font-family: monospace; background: #f4f6f8; }}
	#toolbar {{ padding: 10px 12px; border-bottom: 1px solid #d0d7de; background: #fff; }}
	#graph {{ width: 100vw; height: calc(100vh - 48px); }}
  </style>
</head>
<body>
  <div id=\"toolbar\">nodes: {len(nodes)} | edges: {len(edges)}</div>
  <div id=\"graph\"></div>
  <script>
	const nodes = new vis.DataSet({json.dumps(nodes)});
	const edges = new vis.DataSet({json.dumps(edges)});
	const container = document.getElementById('graph');
	const data = {{ nodes, edges }};
	const options = {{
	  nodes: {{ shape: 'dot', size: 9, font: {{ size: 10, face: 'monospace' }} }},
	  edges: {{
		width: 1,
		arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
		font: {{ size: 9, align: 'middle' }},
		color: {{ color: '#9aa4b2', highlight: '#444' }}
	  }},
	  interaction: {{ hover: true, tooltipDelay: 80, navigationButtons: true }},
	  physics: {{
		forceAtlas2Based: {{ gravitationalConstant: -45, springLength: 120 }},
		maxVelocity: 90,
		solver: 'forceAtlas2Based',
		timestep: 0.35,
		stabilization: {{ iterations: 220 }}
	  }}
	}};
	new vis.Network(container, data, options);
  </script>
</body>
</html>
"""
	output_path.write_text(html, encoding="utf-8")


def main() -> None:
	parser = argparse.ArgumentParser(description="Visualize Joern-exported CPG GraphSON as interactive HTML")
	parser.add_argument("--input", default="joern-output/export-cpg", help="Path to export directory or export.json file")
	parser.add_argument("--output", default="joern-output/cpg-visualization.html", help="Output HTML file path")
	parser.add_argument("--max-nodes", type=int, default=600, help="Limit number of nodes to render (0 means unlimited)")
	parser.add_argument(
		"--edge-types",
		default="",
		help="Comma-separated edge labels to include (e.g., AST,CFG). Empty means include all.",
	)
	args = parser.parse_args()

	input_path = Path(args.input)
	if not input_path.exists():
		raise SystemExit(f"Input path does not exist: {input_path}")

	edge_types = {part.strip() for part in args.edge_types.split(",") if part.strip()}
	export_files = discover_export_files(input_path)
	if not export_files:
		raise SystemExit(f"No export.json found under: {input_path}")

	nodes, edges = build_graph(export_files, args.max_nodes, edge_types)
	write_html(Path(args.output), nodes, edges)

	print(f"Loaded export files: {len(export_files)}")
	print(f"Rendered nodes: {len(nodes)}")
	print(f"Rendered edges: {len(edges)}")
	print(f"Wrote HTML: {args.output}")


if __name__ == "__main__":
	main()
