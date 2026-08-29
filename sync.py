"""
sync.py — reads entries.json and indexes any new entries into ChromaDB + graph.

Run after adding or editing entries:
    python sync.py

Safe to run repeatedly — already-indexed entries are skipped by content hash.
Pass --rebuild to wipe the index and re-embed everything from scratch.
"""

import hashlib
import json
import logging
import os
import sys
from typing import Any, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sync")

# Silence noisy HTTP logs from HuggingFace Hub and httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

ENTRIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entries.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph.builder import add_node, reset_graph
from storage.chroma import add_entry, get_indexed_ids


def entry_id(entry: Dict[str, Any]) -> str:
    """Stable ID derived from entry content — deterministic across runs."""
    canonical = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(canonical.encode()).hexdigest()[:16]


def load_entries() -> list[Dict[str, Any]]:
    if not os.path.exists(ENTRIES_PATH):
        log.warning("entries.json not found at %s", ENTRIES_PATH)
        log.info("Create it with a JSON array of entries and run sync again.")
        return []
    with open(ENTRIES_PATH, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("entries.json must be a JSON array [ {...}, {...} ]")
    log.info("Loaded %d entries from entries.json", len(data))
    return data


def run(rebuild: bool = False) -> Dict[str, int]:
    """
    Index new entries from entries.json into ChromaDB and the graph.
    Returns {"new": int, "skipped": int, "total": int}.
    """
    entries = load_entries()
    if not entries:
        return {"new": 0, "skipped": 0, "total": 0}

    if rebuild:
        log.info("--rebuild: wiping existing index and graph...")
        reset_graph()
        already_indexed: set = set()
    else:
        already_indexed = get_indexed_ids()
        log.info("%d entries already indexed", len(already_indexed))

    new_count = 0
    skip_count = 0

    for entry in entries:
        eid = entry_id(entry)
        if eid in already_indexed:
            skip_count += 1
            continue

        log.info(
            "Indexing  %s  %-12s  %s  [%s]",
            eid,
            entry.get("date", ""),
            entry.get("entry_type", ""),
            entry.get("skill_area", ""),
        )
        add_entry(eid, entry)
        add_node(eid, entry)
        new_count += 1

    log.info("Done — %d new, %d skipped (already up-to-date)", new_count, skip_count)
    if new_count == 0 and skip_count > 0:
        log.info("Tip: edited an existing entry? Run with --rebuild to re-embed it.")

    return {"new": new_count, "skipped": skip_count, "total": len(entries)}


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    run(rebuild=rebuild)
