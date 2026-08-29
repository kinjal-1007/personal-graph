import json
import os
from typing import Any, Dict, List

import networkx as nx
from networkx.readwrite import json_graph

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graph.json")

_graph: nx.Graph = None


def _load_graph() -> nx.Graph:
    global _graph
    if _graph is not None:
        return _graph
    if os.path.exists(GRAPH_PATH):
        with open(GRAPH_PATH, "r") as f:
            data = json.load(f)
        _graph = json_graph.node_link_graph(data)
    else:
        _graph = nx.Graph()
    return _graph


def _save_graph(g: nx.Graph) -> None:
    data = json_graph.node_link_data(g)
    with open(GRAPH_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _edge_reasons(a_data: Dict, b_data: Dict) -> List[str]:
    reasons: List[str] = []
    if a_data.get("entry_type") and a_data["entry_type"] == b_data.get("entry_type"):
        reasons.append(f"entry_type:{a_data['entry_type']}")
    if a_data.get("skill_area") and a_data["skill_area"] == b_data.get("skill_area"):
        reasons.append(f"skill_area:{a_data['skill_area']}")
    shared_tags = set(a_data.get("tags", [])) & set(b_data.get("tags", []))
    for tag in shared_tags:
        reasons.append(f"tag:{tag}")
    return reasons


def reset_graph() -> None:
    """Wipe the in-memory graph and delete graph.json (used before a full re-sync)."""
    global _graph
    _graph = nx.Graph()
    if os.path.exists(GRAPH_PATH):
        os.remove(GRAPH_PATH)


def add_node(entry_id: str, entry: Dict[str, Any]) -> int:
    """
    Add a node and create edges to existing nodes that share
    entry_type, skill_area, or any tag. Returns new edge count.
    """
    g = _load_graph()

    node_data = {
        "date": entry.get("date", ""),
        "entry_type": entry.get("entry_type", ""),
        "context": entry.get("context", ""),
        "skill_area": entry.get("skill_area", ""),
        "insight": entry.get("insight", ""),
        "emotion": entry.get("emotion", ""),
        "project": entry.get("project", ""),
        "impact": entry.get("impact") or "",
        "tags": entry.get("tags", []),
    }
    g.add_node(entry_id, **node_data)

    edges_created = 0
    for existing_id in list(g.nodes):
        if existing_id == entry_id:
            continue
        existing_data = g.nodes[existing_id]
        reasons = _edge_reasons(node_data, dict(existing_data))
        if reasons:
            if g.has_edge(entry_id, existing_id):
                current = g.edges[entry_id, existing_id].get("reasons", [])
                g.edges[entry_id, existing_id]["reasons"] = list(set(current) | set(reasons))
            else:
                g.add_edge(entry_id, existing_id, reasons=reasons, weight=len(reasons))
                edges_created += 1

    _save_graph(g)
    return edges_created


def get_graph() -> nx.Graph:
    return _load_graph()


def reload_graph() -> nx.Graph:
    global _graph
    _graph = None
    return _load_graph()
