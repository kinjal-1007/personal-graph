from collections import Counter
from typing import Any, Dict, List

from graph.builder import get_graph


def get_patterns(top_n: int = 5) -> Dict[str, Any]:
    """
    Return the most frequently occurring entry_types and skill_areas,
    plus the most-connected nodes (hubs in the graph).
    """
    g = get_graph()
    nodes = dict(g.nodes(data=True))

    entry_type_counts: Counter = Counter()
    skill_area_counts: Counter = Counter()
    tag_counts: Counter = Counter()

    for _, data in nodes.items():
        if data.get("entry_type"):
            entry_type_counts[data["entry_type"]] += 1
        if data.get("skill_area"):
            skill_area_counts[data["skill_area"]] += 1
        for tag in data.get("tags", []):
            tag_counts[tag] += 1

    degree_map = dict(g.degree())
    hubs = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:top_n]
    hub_summaries = []
    for node_id, degree in hubs:
        d = nodes.get(node_id, {})
        hub_summaries.append(
            {
                "id": node_id,
                "date": d.get("date", ""),
                "entry_type": d.get("entry_type", ""),
                "skill_area": d.get("skill_area", ""),
                "insight": d.get("insight", ""),
                "connections": degree,
            }
        )

    return {
        "total_entries": g.number_of_nodes(),
        "total_connections": g.number_of_edges(),
        "top_entry_types": entry_type_counts.most_common(top_n),
        "top_skill_areas": skill_area_counts.most_common(top_n),
        "top_tags": tag_counts.most_common(top_n),
        "most_connected_entries": hub_summaries,
    }


def get_timeline(skill_area: str) -> List[Dict[str, Any]]:
    """
    Return all entries that match skill_area (case-insensitive), sorted by date.
    """
    g = get_graph()
    matches = []

    for node_id, data in g.nodes(data=True):
        if data.get("skill_area", "").lower() == skill_area.lower():
            matches.append(
                {
                    "id": node_id,
                    "date": data.get("date", ""),
                    "entry_type": data.get("entry_type", ""),
                    "context": data.get("context", ""),
                    "insight": data.get("insight", ""),
                    "emotion": data.get("emotion", ""),
                    "project": data.get("project", ""),
                    "impact": data.get("impact", ""),
                    "tags": data.get("tags", []),
                }
            )

    matches.sort(key=lambda x: x["date"])
    return matches


def get_entries_by_ids(entry_ids: List[str]) -> List[Dict[str, Any]]:
    """Retrieve full node data for a list of entry IDs."""
    g = get_graph()
    entries = []
    for eid in entry_ids:
        if g.has_node(eid):
            data = dict(g.nodes[eid])
            data["id"] = eid
            entries.append(data)
    return entries
