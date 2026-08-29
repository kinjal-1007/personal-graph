"""
FastMCP server — exposes query tools to Claude Desktop.

Run directly:
    python mcp_server.py

Or via uv (recommended, picks up deps from pyproject.toml):
    uv run mcp run mcp_server.py

Syncs entries.json automatically on startup.
Use the sync_entries tool from Claude to re-sync after adding new entries.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mcp_server")

# Silence noisy HTTP logs from HuggingFace Hub and httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

from fastmcp import FastMCP
from graph.query import get_entries_by_ids
from graph.query import get_patterns as _get_patterns
from graph.query import get_timeline as _get_timeline
from storage.chroma import search as chroma_search
from sync import run as sync_run


@asynccontextmanager
async def lifespan(server):
    log.info("Startup: syncing entries.json (new entries only)...")
    result = sync_run(rebuild=False)
    log.info(
        "Startup sync complete — %d new, %d skipped, %d total",
        result["new"],
        result["skipped"],
        result["total"],
    )
    yield
    log.info("Shutting down.")


mcp = FastMCP("personal-growth-graph", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Tool 1 — Semantic search
# ---------------------------------------------------------------------------

@mcp.tool()
def search_memories(query: str) -> list[dict]:
    """
    Search your growth journal by meaning, not just keywords.

    Returns the 5 most semantically similar entries with a similarity score
    (1.0 = identical, 0.0 = unrelated).

    Args:
        query: What you're looking for, e.g. "times I rushed under deadline pressure"
    """
    log.info("search_memories: query=%r", query)
    hits = chroma_search(query, n_results=5)
    if not hits:
        return [{"message": "No entries indexed yet. Add entries to entries.json and run sync."}]

    results = []
    for hit in hits:
        meta = hit.get("meta", {})
        results.append(
            {
                "id": hit["id"],
                "similarity": hit["similarity"],
                "date": meta.get("date", ""),
                "entry_type": meta.get("entry_type", ""),
                "skill_area": meta.get("skill_area", ""),
                "project": meta.get("project", ""),
                "emotion": meta.get("emotion", ""),
                "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
                "summary": hit.get("document", ""),
            }
        )
    log.info("search_memories: returning %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# Tool 2 — Patterns
# ---------------------------------------------------------------------------

@mcp.tool()
def get_patterns() -> str:
    """
    Analyse the growth graph and surface recurring themes.

    Returns a plain-text summary of the most common entry types, skill areas,
    tags, and the most-connected entries (ones that share context with many others).

    Use this for questions like "what do I repeat the most?" or
    "where am I growing vs. stagnating?"
    """
    log.info("get_patterns called")
    data = _get_patterns(top_n=5)

    if data["total_entries"] == 0:
        return "No entries indexed yet. Add entries to entries.json and run sync_entries."

    lines = [
        f"Total entries: {data['total_entries']}",
        f"Total connections: {data['total_connections']}",
        "",
        "--- Top entry types ---",
    ]
    for etype, count in data["top_entry_types"]:
        lines.append(f"  {etype}: {count}x")

    lines += ["", "--- Top skill areas ---"]
    for skill, count in data["top_skill_areas"]:
        lines.append(f"  {skill}: {count}x")

    lines += ["", "--- Top tags ---"]
    for tag, count in data["top_tags"]:
        lines.append(f"  #{tag}: {count}x")

    lines += ["", "--- Most connected entries ---"]
    for hub in data["most_connected_entries"]:
        lines.append(
            f"  [{hub['date']}] {hub['entry_type']} | {hub['skill_area']} "
            f"— \"{hub['insight'][:80]}\" ({hub['connections']} connections)"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3 — Timeline for a skill area
# ---------------------------------------------------------------------------

@mcp.tool()
def get_timeline(skill_area: str) -> list[dict]:
    """
    Show every entry that touched a given skill area, in chronological order.

    Useful for: "How has my communication skill evolved?" or
    "Am I actually improving at system design, or repeating the same gap?"

    Args:
        skill_area: Skill area to trace, e.g. "process discipline"
    """
    log.info("get_timeline: skill_area=%r", skill_area)
    entries = _get_timeline(skill_area)
    if not entries:
        return [{"message": f"No entries found for skill_area='{skill_area}'."}]
    log.info("get_timeline: %d entries found", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Tool 4 — Interview story builder
# ---------------------------------------------------------------------------

@mcp.tool()
def get_interview_story(topic: str) -> str:
    """
    Find the 3 most relevant journal entries for a topic and format them
    as interview-ready stories.

    Each story:
      WHEN: date + project
      WHAT HAPPENED: context
      WHAT I LEARNED: insight
      HOW I CHANGED: impact

    Args:
        topic: What you want a story about, e.g. "handling pressure under a deadline"
    """
    log.info("get_interview_story: topic=%r", topic)
    hits = chroma_search(topic, n_results=3)
    if not hits:
        return "No matching entries found."

    ids = [h["id"] for h in hits]
    entries = get_entries_by_ids(ids)

    id_order = {eid: i for i, eid in enumerate(ids)}
    entries.sort(key=lambda e: id_order.get(e["id"], 99))

    stories = []
    for i, entry in enumerate(entries, 1):
        impact = entry.get("impact") or "Not recorded."
        stories.append(
            f"--- Story {i} ---\n"
            f"WHEN:           {entry.get('date', 'unknown')} | {entry.get('project', '')}\n"
            f"TYPE:           {entry.get('entry_type', '')}\n"
            f"WHAT HAPPENED:  {entry.get('context', '')}\n"
            f"WHAT I LEARNED: {entry.get('insight', '')}\n"
            f"HOW I CHANGED:  {impact}\n"
            f"EMOTION:        {entry.get('emotion', '')}\n"
            f"TAGS:           {', '.join(entry.get('tags', []))}"
        )

    return "\n\n".join(stories)


# ---------------------------------------------------------------------------
# Tool 5 — Re-sync after editing entries.json
# ---------------------------------------------------------------------------

@mcp.tool()
def sync_entries(rebuild: bool = False) -> str:
    """
    Re-index entries.json into ChromaDB and the graph.

    Call this after you've added new entries to entries.json.

    Args:
        rebuild: If True, wipe the existing index and re-embed everything.
                 Use this if you edited or deleted existing entries.
                 Defaults to False (only indexes new entries).
    """
    log.info("sync_entries called (rebuild=%s)", rebuild)
    result = sync_run(rebuild=rebuild)
    msg = f"Sync complete — {result['new']} new entries indexed, {result['skipped']} already up-to-date ({result['total']} total)."
    if result["new"] == 0 and result["skipped"] > 0:
        msg += " Tip: if you edited an existing entry, call sync_entries(rebuild=True)."
    log.info(msg)
    return msg


if __name__ == "__main__":
    mcp.run()
