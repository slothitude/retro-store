# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RetroZone — Australian retro gaming store with two components sharing one SQLite database:
1. **Flask web store** (`app.py`, `routes/`, `templates/`) — customer-facing e-commerce with Stripe
2. **Tkinter desktop manager** (`retrozone_manager/`) — admin GUI with Claude AI automation

## Commands

```bash
# Run Flask store
python app.py                          # http://localhost:5000

# Run desktop manager
python retrozone_manager/main.py       # Tkinter GUI

# Run MCP server (stdio transport, used by Claude CLI)
python -m retrozone_manager.mcp_server.server

# Install dependencies
pip install -r requirements.txt
```

No test suite or linter configured.

## Architecture

### Dual-App, Shared Database
Both apps read/write `retro_store.db` (SQLite WAL mode, foreign keys on). No ORM — raw SQL via `db.py` (Flask) and `db_layer.py` (Tkinter). Each query opens/closes its own connection.

### Three-Phase Pricing Model
Products use batch-based pricing with three phases controlled by `arrives_at`/`expires_at` timestamps:
- **PRE-ORDER** (`cost × 1.10`) — batch ordered but not arrived
- **IN-STOCK** (`cost × 1.40`) — standard retail margin
- **CLEARANCE** (`cost`) — expires within 48h, dump stock

Phase logic lives in `db.py:get_batch_phase()`. Flask routes apply batch pricing dynamically to override product list prices.

### Claude Integration (Tkinter App)
- **`ClaudeClient`** wraps `claude -p -` as a subprocess (stdin piping, temp file for system prompt)
- Uses `shell=True` with `CREATE_NEW_PROCESS_GROUP` on Windows for proper timeout cleanup
- JSON output parsed into `ClaudeResponse` dataclass

### Workflow Engine
State machine running in background threads with approval gates:
- Step types: `analyze` (read-only) → `propose` (needs approval) → `execute` (runs SQL)
- `research` step type enables MCP tools (300s timeout, `--allowedTools`)
- UI updates via `app.after(0, callback)` from worker threads
- Workflows subclass `BaseWorkflow` — implement `get_steps()`, `build_analyze_prompt()`, optionally `build_propose_prompt()`

### MCP Server (retro-tools)
FastMCP stdio server with 13 tools:
- **Scrapers** (`mcp_server/scrapers/`) — fallback chain: direct httpx → web-reader Playwright → SearXNG
- **SearXNG** runs on Lappy (192.168.0.33:8888), accessed via web-reader MCP (SSE at :8003)
- **Rate limiting**: 3s minimum between SearXNG requests (`base.py:_throttle_search()`)
- **MCP-over-SSE protocol**: connect to SSE stream → extract session URL → POST JSON-RPC → read response

### System Prompts
Built dynamically in `prompts/system_context.py`:
- `build_system_prompt()` — DB schema, ethos, store model, rules, live store state
- `build_system_prompt_with_tools()` — adds MCP tool capabilities and usage rules
- Every evaluation filters through ROI, Velocity, and Ethos lenses

### Panel System (Tkinter)
Panels are lazy-loaded from `panels/` by class name convention (`key + "Panel"`). Non-chat panels wrapped in `ScrollableFrame`. Registered in `app.py:_get_panel()`.

## Key Gotchas

- **Windows subprocess**: `claude` is a `.cmd` wrapper — requires `shell=True`. `CREATE_NEW_PROCESS_GROUP` needed to kill child processes on timeout.
- **Paths**: use forward slashes in Python. `BASE_DIR` is the retro-store root.
- **Tkinter threading**: never touch widgets from worker threads — always use `app.after(0, ...)`.
- **MCP server cwd**: `.mcp.json` sets `"cwd": "."` — must run Claude from the retro-store directory.
- **Scraper blocking**: eBay/Alibaba block direct httpx scraping (403). Scrapers fall back through web-reader → SearXNG.
- **Budget tracking**: per-call via `--max-budget-usd`. Session accumulation in StatusBar.
- **No test suite**: workflows tested manually via GUI or MockApp harness.
