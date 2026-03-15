from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal, TypeAlias

import pandas as pd


NodeId: TypeAlias = int | str
PDGEdges: TypeAlias = tuple[list[int], list[int]]
GraphType: TypeAlias = Literal["reftype", "ast", "pdg", "cfgcdg", "all"]

REPO_ROOT = Path("/app")
CACHE_ROOT = REPO_ROOT / "cache"
EMPTY_CODE_VALUES = {"", "<empty>"}
NODE_PRIORITY = {
    "CONTROL_STRUCTURE": 100,
    "RETURN": 95,
    "CALL": 90,
    "METHOD": 85,
    "METHOD_REF": 80,
    "TYPE_DECL": 70,
    "LOCAL": 60,
    "IDENTIFIER": 50,
    "LITERAL": 40,
    "BLOCK": 10,
}


def joern_graph_extraction(
    source_file_path: str, joern_file_path: str
) -> tuple[pd.DataFrame, PDGEdges]:
    source_path = _resolve_path(source_file_path)
    joern_base_path = _resolve_path(joern_file_path)
    cache_dir = CACHE_ROOT / joern_base_path.name
    cache_dir.mkdir(parents=True, exist_ok=True)

    raw_nodes = _read_json(joern_base_path.with_suffix(".nodes.json"))
    raw_edges = _read_json(joern_base_path.with_suffix(".edges.json"))
    _write_json(cache_dir / "01_raw_nodes.json", raw_nodes)
    _write_json(cache_dir / "01_raw_edges.json", raw_edges)

    nodes = normalize_nodes(raw_nodes)
    edges = normalize_edges(raw_edges)
    _write_frame(cache_dir / "02_nodes_normalized.csv", nodes)
    _write_frame(cache_dir / "02_edges_normalized.csv", edges)

    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    nodes = enrich_nodes(nodes, edges, source_lines)
    _write_frame(cache_dir / "03_nodes_enriched.csv", nodes)

    edges = attach_line_numbers(nodes, edges)
    _write_frame(cache_dir / "04_edges_with_lines.csv", edges)

    statement_nodes = build_statement_nodes(nodes)
    dependency_line_edges = build_line_pdg_edges(edges)
    graph_line_edges = dependency_line_edges
    graph_kind = "pdg"
    if graph_line_edges.empty:
        graph_line_edges = build_fallback_line_edges(edges)
        graph_kind = "semantic-fallback"
    if not graph_line_edges.empty:
        statement_nodes = drop_lone_nodes(statement_nodes, graph_line_edges)
    _write_frame(cache_dir / "05_statement_nodes.csv", statement_nodes)
    _write_frame(cache_dir / "05_statement_edges.csv", graph_line_edges)
    _write_frame(cache_dir / "05_dependency_edges.csv", dependency_line_edges)

    pdg_nodes, pdg_edges = build_pdg(statement_nodes, graph_line_edges, dependency_line_edges)
    _write_frame(cache_dir / "06_pdg_nodes.csv", pdg_nodes)
    _write_json(
        cache_dir / "06_pdg_edges.json",
        {"outnode": pdg_edges[0], "innode": pdg_edges[1]},
    )
    _write_json(
        cache_dir / "summary.json",
        {
            "source_file": str(source_path),
            "joern_base_path": str(joern_base_path),
            "node_count": int(len(nodes)),
            "edge_count": int(len(edges)),
            "statement_node_count": int(len(statement_nodes)),
            "pdg_edge_count": int(len(pdg_edges[0])),
            "graph_kind": graph_kind,
        },
    )

    return pdg_nodes, pdg_edges


def get_node_edges(
    source_file_path: str, joern_file_path: str, verbose: int = 0
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    del verbose
    source_path = _resolve_path(source_file_path)
    joern_base_path = _resolve_path(joern_file_path)

    try:
        raw_nodes = _read_json(joern_base_path.with_suffix(".nodes.json"))
        raw_edges = _read_json(joern_base_path.with_suffix(".edges.json"))
    except FileNotFoundError:
        return None, None

    normalized_edges = normalize_edges(raw_edges)
    source_lines = source_path.read_text(encoding="utf-8").splitlines()
    nodes = enrich_nodes(normalize_nodes(raw_nodes), normalized_edges, source_lines)
    edges = attach_line_numbers(nodes, normalized_edges)
    return nodes, edges


def normalize_nodes(raw_nodes: Any) -> pd.DataFrame:
    node_rows: list[dict[str, Any]] = []
    for node in _as_sequence(raw_nodes):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id", node.get("_id"))
        if node_id is None:
            continue
        label = _stringify(node.get("_label", ""))
        name = _stringify(node.get("name", ""))
        code = _stringify(node.get("code", ""))
        full_name = _stringify(node.get("fullName", ""))
        if code in EMPTY_CODE_VALUES:
            code = name or full_name or label
        node_rows.append(
            {
                "id": node_id,
                "_label": label,
                "name": name,
                "code": code,
                "lineNumber": _coerce_int(node.get("lineNumber")),
                "columnNumber": _coerce_int(node.get("columnNumber")),
                "controlStructureType": _stringify(
                    node.get("controlStructureType", "")
                ),
                "typeFullName": _stringify(node.get("typeFullName", "")),
                "fullName": full_name,
                "filename": _stringify(node.get("filename", "")),
                "order": _coerce_int(node.get("order")),
            }
        )

    nodes = pd.DataFrame.from_records(node_rows)
    if nodes.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "_label",
                "name",
                "code",
                "lineNumber",
                "columnNumber",
                "controlStructureType",
                "typeFullName",
                "fullName",
                "filename",
                "order",
                "node_label",
            ]
        )

    nodes = nodes.drop_duplicates(subset=["id"], keep="first").copy()
    nodes["lineNumber"] = pd.Series(nodes["lineNumber"], dtype="Int64")
    nodes["columnNumber"] = pd.Series(nodes["columnNumber"], dtype="Int64")
    nodes["order"] = pd.Series(nodes["order"], dtype="Int64")
    nodes["node_label"] = nodes.apply(build_node_label, axis=1)
    return nodes


def normalize_edges(raw_edges: Any) -> pd.DataFrame:
    edge_rows: list[dict[str, Any]] = []
    for edge in _as_sequence(raw_edges):
        if isinstance(edge, dict):
            edge_type = _stringify(edge.get("etype", edge.get("label", "")))
            innode = _extract_endpoint_id(edge.get("innode", edge.get("src")))
            outnode = _extract_endpoint_id(edge.get("outnode", edge.get("dst")))
            dataflow = edge.get("dataflow", "")
        elif isinstance(edge, (list, tuple)) and len(edge) >= 3:
            innode = _extract_endpoint_id(edge[0])
            outnode = _extract_endpoint_id(edge[1])
            edge_type = _stringify(edge[2])
            dataflow = edge[3] if len(edge) > 3 else ""
        else:
            continue

        if innode is None or outnode is None or not edge_type:
            continue

        edge_rows.append(
            {
                "innode": innode,
                "outnode": outnode,
                "etype": edge_type,
                "dataflow": _stringify(dataflow),
            }
        )

    edges = pd.DataFrame.from_records(edge_rows)
    if edges.empty:
        return pd.DataFrame(
            columns=["innode", "outnode", "etype", "dataflow", "line_in", "line_out"]
        )
    return edges.drop_duplicates().copy()


def enrich_nodes(
    nodes: pd.DataFrame, edges: pd.DataFrame, source_lines: list[str]
) -> pd.DataFrame:
    del source_lines
    if nodes.empty:
        return nodes

    enriched = nodes.copy()
    inferred_lines = infer_missing_line_numbers(enriched, edges)
    enriched["lineNumber"] = enriched["id"].map(inferred_lines)
    enriched["lineNumber"] = pd.Series(enriched["lineNumber"], dtype="Int64")
    enriched["code"] = enriched.apply(
        lambda row: row["code"] if row["code"] not in EMPTY_CODE_VALUES else row["name"],
        axis=1,
    )
    enriched["code"] = enriched["code"].fillna("")
    enriched = enriched[~enriched["_label"].isin(["COMMENT", "FILE"])]
    enriched["node_label"] = enriched.apply(build_node_label, axis=1)
    return enriched.reset_index(drop=True)


def attach_line_numbers(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return edges.copy()

    line_map = nodes.set_index("id")["lineNumber"].to_dict()
    edges_with_lines = edges.copy()
    edges_with_lines["line_in"] = edges_with_lines["innode"].map(line_map)
    edges_with_lines["line_out"] = edges_with_lines["outnode"].map(line_map)
    edges_with_lines = edges_with_lines[
        ~edges_with_lines["etype"].isin(["CONTAINS", "SOURCE_FILE", "DOMINATE", "POST_DOMINATE"])
    ]
    edges_with_lines = edges_with_lines[
        edges_with_lines["line_in"].notna() | edges_with_lines["line_out"].notna()
    ].copy()
    edges_with_lines["line_in"] = pd.Series(edges_with_lines["line_in"], dtype="Int64")
    edges_with_lines["line_out"] = pd.Series(edges_with_lines["line_out"], dtype="Int64")
    return edges_with_lines.reset_index(drop=True)


def build_statement_nodes(nodes: pd.DataFrame) -> pd.DataFrame:
    line_nodes = nodes[nodes["lineNumber"].notna()].copy()
    if line_nodes.empty:
        return pd.DataFrame(columns=["id", "lineNumber", "code", "_label", "node_label"])

    line_nodes["priority"] = line_nodes["_label"].map(NODE_PRIORITY).fillna(0)
    line_nodes["code_len"] = line_nodes["code"].fillna("").str.len()
    line_nodes["columnNumberSortable"] = line_nodes["columnNumber"].fillna(10**9)
    line_nodes = line_nodes.sort_values(
        by=["lineNumber", "priority", "code_len", "columnNumberSortable", "id"],
        ascending=[True, False, False, True, True],
    )
    statement_nodes = line_nodes.groupby("lineNumber", as_index=False).first()
    statement_nodes["id"] = statement_nodes["lineNumber"].astype(int)
    return statement_nodes[
        ["id", "lineNumber", "code", "_label", "node_label", "filename", "fullName"]
    ].reset_index(drop=True)


def build_line_pdg_edges(edges: pd.DataFrame) -> pd.DataFrame:
    pdg_edges = rdg(edges, "pdg").copy()
    if pdg_edges.empty:
        return pd.DataFrame(columns=["innode", "outnode", "etype"])

    pdg_edges["innode"] = pdg_edges["line_in"]
    pdg_edges["outnode"] = pdg_edges["line_out"]
    pdg_edges["etype"] = pdg_edges["etype"].replace({"REACHING_DEF": "DDG"})
    pdg_edges = pdg_edges[pdg_edges["innode"].notna() & pdg_edges["outnode"].notna()].copy()
    pdg_edges["innode"] = pdg_edges["innode"].astype(int)
    pdg_edges["outnode"] = pdg_edges["outnode"].astype(int)
    pdg_edges = pdg_edges[pdg_edges["innode"] != pdg_edges["outnode"]]
    return pdg_edges[["innode", "outnode", "etype"]].drop_duplicates().reset_index(drop=True)


def build_fallback_line_edges(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=["innode", "outnode", "etype"])

    fallback_types = ["AST", "ARGUMENT", "RECEIVER", "REF", "CONDITION", "BINDS", "CAPTURE", "CFG"]
    fallback_edges = edges[edges["etype"].isin(fallback_types)].copy()
    if fallback_edges.empty:
        return pd.DataFrame(columns=["innode", "outnode", "etype"])

    fallback_edges["innode"] = fallback_edges["line_in"]
    fallback_edges["outnode"] = fallback_edges["line_out"]
    fallback_edges = fallback_edges[
        fallback_edges["innode"].notna() & fallback_edges["outnode"].notna()
    ].copy()
    fallback_edges["innode"] = fallback_edges["innode"].astype(int)
    fallback_edges["outnode"] = fallback_edges["outnode"].astype(int)
    fallback_edges = fallback_edges[fallback_edges["innode"] != fallback_edges["outnode"]]
    return fallback_edges[["innode", "outnode", "etype"]].drop_duplicates().reset_index(drop=True)


def build_pdg(
    statement_nodes: pd.DataFrame,
    graph_line_edges: pd.DataFrame,
    dependency_line_edges: pd.DataFrame,
) -> tuple[pd.DataFrame, PDGEdges]:
    if statement_nodes.empty:
        empty_nodes = pd.DataFrame(
            columns=["index", "id", "lineNumber", "code", "_label", "node_label", "data", "control"]
        )
        return empty_nodes, ([], [])

    data_lookup, control_lookup = build_dependency_lookup(dependency_line_edges)
    pdg_nodes = statement_nodes.copy().sort_values("id").reset_index(drop=True)
    pdg_nodes["data"] = pdg_nodes["id"].map(data_lookup).apply(_normalize_list_cell)
    pdg_nodes["control"] = pdg_nodes["id"].map(control_lookup).apply(_normalize_list_cell)
    pdg_nodes = pdg_nodes.reset_index()

    node_index = pd.Series(pdg_nodes.index.values, index=pdg_nodes.id).to_dict()
    mapped_edges = graph_line_edges.copy()
    mapped_edges["innode"] = mapped_edges["innode"].map(node_index)
    mapped_edges["outnode"] = mapped_edges["outnode"].map(node_index)
    mapped_edges = mapped_edges.dropna(subset=["innode", "outnode"])
    mapped_edges["innode"] = mapped_edges["innode"].astype(int)
    mapped_edges["outnode"] = mapped_edges["outnode"].astype(int)
    pdg_edges = (mapped_edges["outnode"].tolist(), mapped_edges["innode"].tolist())
    return pdg_nodes, pdg_edges


def build_dependency_lookup(
    pdg_line_edges: pd.DataFrame,
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    if pdg_line_edges.empty:
        return {}, {}

    reversed_edges = pdg_line_edges.rename(columns={"innode": "outnode", "outnode": "innode"})
    undirected_edges = pd.concat([pdg_line_edges, reversed_edges], ignore_index=True)
    dependency_map: defaultdict[tuple[int, str], set[int]] = defaultdict(set)
    for edge in undirected_edges.to_dict("records"):
        innode = _coerce_int(edge.get("innode"))
        outnode = _coerce_int(edge.get("outnode"))
        edge_type = _stringify(edge.get("etype"))
        if innode is None or outnode is None or not edge_type:
            continue
        dependency_map[(innode, edge_type)].add(outnode)

    data_lookup: dict[int, list[int]] = {}
    control_lookup: dict[int, list[int]] = {}
    for (line_number, edge_type), neighbours in dependency_map.items():
        values = sorted(neighbour for neighbour in neighbours if neighbour != line_number)
        if edge_type == "DDG":
            data_lookup[line_number] = values
        if edge_type == "CDG":
            control_lookup[line_number] = values
    return data_lookup, control_lookup


def infer_missing_line_numbers(nodes: pd.DataFrame, edges: pd.DataFrame) -> dict[NodeId, int | None]:
    line_map: dict[NodeId, int | None] = {}
    for row in nodes[["id", "lineNumber"]].to_dict("records"):
        node_id = _extract_endpoint_id(row.get("id"))
        if node_id is None:
            continue
        line_map[node_id] = _coerce_int(row.get("lineNumber"))

    adjacency: defaultdict[NodeId, set[NodeId]] = defaultdict(set)
    edge_types: tuple[GraphType, ...] = ("ast", "reftype", "all")
    for edge_type in edge_types:
        related_edges = rdg(edges, edge_type)
        for edge in related_edges[["innode", "outnode"]].to_dict("records"):
            innode = _extract_endpoint_id(edge.get("innode"))
            outnode = _extract_endpoint_id(edge.get("outnode"))
            if innode is None or outnode is None:
                continue
            adjacency[innode].add(outnode)
            adjacency[outnode].add(innode)

    for _ in range(8):
        changed = False
        for node_id, line_number in list(line_map.items()):
            if line_number is not None:
                continue
            neighbour_lines = [
                line_map[neighbour]
                for neighbour in adjacency.get(node_id, set())
                if line_map.get(neighbour) is not None
            ]
            if not neighbour_lines:
                continue
            inferred_line = Counter(neighbour_lines).most_common(1)[0][0]
            line_map[node_id] = inferred_line
            changed = True
        if not changed:
            break

    return line_map


def neighbour_nodes(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    nodeids: list[NodeId],
    hop: int = 1,
    intermediate: bool = True,
) -> dict[NodeId, list[NodeId]]:
    del nodes
    adjacency: defaultdict[NodeId, set[NodeId]] = defaultdict(set)
    for edge in edges[["innode", "outnode"]].to_dict("records"):
        innode = _extract_endpoint_id(edge.get("innode"))
        outnode = _extract_endpoint_id(edge.get("outnode"))
        if innode is None or outnode is None:
            continue
        adjacency[innode].add(outnode)
        adjacency[outnode].add(innode)

    neighbours: dict[NodeId, list[NodeId]] = {}
    for node_id in nodeids:
        visited = {node_id}
        frontier = {node_id}
        collected: list[NodeId] = []
        for _ in range(hop):
            next_frontier: set[NodeId] = set()
            for frontier_node in frontier:
                next_frontier.update(adjacency.get(frontier_node, set()))
            next_frontier -= visited
            if intermediate:
                collected.extend(sorted(next_frontier))
            frontier = next_frontier
            visited.update(next_frontier)
            if not frontier:
                break
        if not intermediate:
            collected = sorted(frontier)
        neighbours[node_id] = collected
    return neighbours


def rdg(edges: pd.DataFrame, gtype: GraphType) -> pd.DataFrame:
    if edges.empty:
        return edges.copy()
    if gtype == "reftype":
        return edges[edges.etype.isin(["EVAL_TYPE", "REF"])]
    if gtype == "ast":
        return edges[edges.etype == "AST"]
    if gtype == "pdg":
        return edges[edges.etype.isin(["REACHING_DEF", "CDG", "DDG"])]
    if gtype == "cfgcdg":
        return edges[edges.etype.isin(["CFG", "CDG"])]
    return edges[edges.etype.isin(["REACHING_DEF", "CDG", "DDG", "AST", "EVAL_TYPE", "REF"])]


def assign_line_num_to_local(
    nodes: pd.DataFrame, edges: pd.DataFrame, code: list[str]
) -> dict[NodeId, int]:
    del code
    inferred = infer_missing_line_numbers(nodes, edges)
    return {node_id: line for node_id, line in inferred.items() if line is not None}


def drop_lone_nodes(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty or edges.empty:
        return nodes.iloc[0:0].copy()
    return nodes[(nodes.id.isin(edges.innode)) | (nodes.id.isin(edges.outnode))].copy()


def tokenise(s: str) -> str:
    spec_char = re.compile(r"[^a-zA-Z0-9\s]")
    camelcase = re.compile(r".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)")
    spec_split = re.split(spec_char, s)
    space_split = " ".join(spec_split).split()

    def camel_case_split(identifier: str) -> list[str]:
        return [match.group(0) for match in re.finditer(camelcase, identifier)]

    camel_split = [part for item in [camel_case_split(word) for word in space_split] for part in item]
    remove_single = [item for item in camel_split if len(item) > 1]
    return " ".join(remove_single)


def build_node_label(row: pd.Series) -> str:
    line_number = row.get("lineNumber")
    line_part = "" if pd.isna(line_number) else str(int(line_number))
    return f"{row.get('_label', '')}_{line_part}: {row.get('code', '')}"


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    export_frame = frame.copy()
    for column in export_frame.columns:
        export_frame[column] = export_frame[column].apply(_cache_cell_value)
    export_frame.to_csv(path, index=False)


def _cache_cell_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value)
    if pd.isna(value):
        return ""
    return value


def _json_default(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _as_sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ["nodes", "edges", "data"]:
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        return [value]
    return []


def _extract_endpoint_id(value: Any) -> NodeId | None:
    if isinstance(value, dict):
        return value.get("id", value.get("_id"))
    if isinstance(value, (int, str)):
        return value
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def _normalize_list_cell(value: Any) -> list[int]:
    if isinstance(value, list):
        return value
    return []


if __name__ == "__main__":
    pdg_nodes, pdg_edges = joern_graph_extraction(
        "examples/sample.py",
        "joern-output/latest/examples",
    )
    print(pdg_nodes)
    print(pdg_edges)