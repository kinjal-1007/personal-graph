# Personal Growth Graph

A local journal for experiences — mistakes, wins, reflections, insights — queryable through Claude Desktop via MCP.

No frontend. No paid APIs. No HTTP server. Everything runs on your machine.

---

## Getting started

This repo ships with no journal data. To make it yours:

1. **Clone it:**
   ```bash
   git clone https://github.com/kinjal-1007/personal-graph.git
   cd personal-graph
   ```
2. **Install dependencies** — see [Setup](#setup) below.
3. **Create your own `entries.json`** in the project root — a JSON array following the [Entry schema](#entry-schema). Start with one entry, or a handful you remember off the top of your head.
4. **Index it:** `python sync.py`
5. **Connect Claude Desktop** — see [Connecting Claude Desktop](#connecting-claude-desktop).
6. **Ask Claude about your own experience** — see [What to ask Claude](#what-to-ask-claude).

`entries.json`, `graph/graph.json`, and `storage/chroma_store/` are all listed in `.gitignore` — your journal never gets committed, even by accident. See [Privacy & your data](#privacy--your-data).

---

## How it works

```
entries.json   ← paste your entries here (a JSON array)
     ↓
python sync.py ← indexes new entries into ChromaDB + graph
     ↓
python mcp_server.py ← Claude Desktop queries this
```

| Layer | Technology | Purpose |
|---|---|---|
| Source of truth | entries.json | You own the data, edit directly |
| Vector store | ChromaDB | Semantic similarity search |
| Graph store | NetworkX + graph.json | Relationship mapping between entries |
| Embeddings | all-MiniLM-L6-v2 (HuggingFace) | Local, free, runs offline |
| MCP server | FastMCP | Exposes tools to Claude Desktop |

---

## Setup

**Option A — pip + venv (if you already have a venv active):**
```bash
pip install -r requirements.txt
python sync.py          # index entries
python mcp_server.py    # start MCP server
```

**Option B — uv (recommended, no manual venv needed):**
```bash
uv sync                         # installs deps from pyproject.toml
uv run python sync.py           # index entries
uv run mcp run mcp_server.py    # start MCP server
```

---

## Entry schema

`entries.json` is a JSON array. Paste new objects into it whenever you want to log an experience.
Only `impact` is optional.

```json
[
  {
    "date": "2024-01-15",
    "entry_type": "mistake",
    "context": "Pushed to prod on a Friday without PR review",
    "skill_area": "process discipline",
    "insight": "Never deploy under pressure — the pressure is the signal to slow down",
    "emotion": "stressed",
    "project": "auth system",
    "impact": "Rolled back in 20 mins; added mandatory review gate",
    "tags": ["deployment", "process", "pressure"]
  }
]
```

`entry_type` must be one of: `mistake` | `win` | `learning` | `reflection` | `insight`

---

## Workflow: adding new entries

1. Open `entries.json`
2. Paste a new JSON object into the array
3. Run `python sync.py` — only new entries are embedded (fast)
4. If `mcp_server.py` was already running, restart it, then **restart Claude Desktop** — Claude Desktop holds the connection open and won't see the new server process until restarted

If you edited or deleted an existing entry, run with `--rebuild`:
```bash
python sync.py --rebuild
```

---

## Connecting Claude Desktop

1. Open **Claude Desktop → Settings → Developer → Edit Config**
2. Add this block to `claude_desktop_config.json`:

**With uv (recommended):**
```json
{
  "mcpServers": {
    "personal-growth-graph": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/personal-graph", "mcp", "run", "mcp_server.py"]
    }
  }
}
```

**With venv Python:**
```json
{
  "mcpServers": {
    "personal-growth-graph": {
      "command": "/absolute/path/to/personal-graph/venv/bin/python",
      "args": ["/absolute/path/to/personal-graph/mcp_server.py"]
    }
  }
}
```

3. Restart Claude Desktop — the 5 tools will appear automatically.

---

## What to ask Claude

### `search_memories`
> "Find entries about times I handled pressure badly"
> "Show me anything related to architecture decisions"

### `get_patterns`
> "What do I repeat the most?"
> "What is my biggest recurring skill gap?"
> "Where am I growing vs. stagnating?"

### `get_timeline`
> "How has my system design thinking evolved over time?"
> "Show me all entries related to infrastructure reliability"

### `get_interview_story`
> "Give me a story about a time I made a production mistake"
> "What's a good example of a win I had under pressure?"
> "Tell me about my journey with distributed systems"

### `sync_entries`
> "Sync my entries" — re-indexes entries.json without restarting the server

---

## File structure

```
personal_graph/
├── entries.json         ← your data lives here (gitignored — you create this)
├── sync.py              ← index new entries: python sync.py
├── mcp_server.py        ← MCP server for Claude Desktop
├── graph/
│   ├── builder.py       NetworkX: add nodes, create edges, persist graph.json
│   ├── query.py         NetworkX: patterns, timeline, entry lookup
│   └── graph.json       auto-created on first sync (gitignored)
├── storage/
│   ├── chroma.py        ChromaDB: embed, upsert, search
│   └── chroma_store/    auto-created by ChromaDB (gitignored)
├── models/
│   └── entry.py         Pydantic schema for GrowthEntry
└── requirements.txt
```

---

## Edge logic (how the graph connects entries)

Two entries get connected when they share:
- the same `entry_type`
- the same `skill_area`
- one or more `tags`

The more overlap, the higher the edge weight. `get_patterns` uses this to surface which entries are most interconnected — your real recurring themes.

---

## Privacy & your data

Everything that could contain your personal experiences is excluded from git via `.gitignore`:

- `entries.json` — your raw journal entries
- `graph/graph.json` — the relationship graph built from them
- `storage/chroma_store/` — the vector embeddings of your entries
