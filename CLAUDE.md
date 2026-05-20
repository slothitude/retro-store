# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RetroMonkey — Australian retro gaming store with two components sharing one SQLite database:
1. **Flask web store** (`app.py`, `routes/`, `templates/`) — customer-facing e-commerce with Stripe
2. **Tkinter desktop manager** (`retrozone_manager/`) — admin GUI with Claude AI automation

**Live site**: https://retromonkey.ddns.net (Oracle Cloud, Caddy reverse proxy + auto-TLS)

## Commands

```bash
# Run Flask store (dev)
python app.py                          # http://localhost:5555

# Run desktop manager
python retrozone_manager/main.py       # Tkinter GUI

# Run MCP server (stdio transport, used by Claude CLI)
python -m retrozone_manager.mcp_server.server

# Install dependencies
pip install -r requirements.txt

# Deploy to Oracle
git push origin master
ssh -i ~/.oci/retromonkey_ssh_key ubuntu@168.138.8.0 "cd /opt/retro-store && git pull && sudo systemctl restart retrozone"

# Install/Manage backups (Windows Task Scheduler, daily 3AM)
python backup.py --install
python backup.py --uninstall
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

### Flask Blueprints (7)
| Blueprint | File | Purpose |
|-----------|------|---------|
| `store_bp` | `routes/store.py` | Products, cart, checkout, Stripe webhook |
| `admin_bp` | `routes/admin.py` | Dashboard, product CRUD, orders, batches |
| `accounting_bp` | `routes/accounting.py` | Expenses, BAS, P&L, CSV export |
| `customers_bp` | `routes/customers.py` | Registration, login, order history |
| `kb_bp` | `routes/kb.py` | Knowledge base (FTS5 search) |
| `tickets_bp` | `routes/tickets.py` | Support tickets |
| `chat_bp` | `routes/chat.py` | Live chat widget |

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

### Deployment (Oracle Cloud)
- **Git**: `https://github.com/slothitude/retro-store.git`
- **Server**: Oracle Cloud Free Tier (ARM), Ubuntu, IP `168.138.8.0`
- **SSH**: `ssh -i ~/.oci/retromonkey_ssh_key ubuntu@168.138.8.0`
- **Service**: `retrozone.service` — gunicorn (2 workers) bound to `127.0.0.1:5000`
- **Reverse proxy**: Caddy with auto-TLS (Let's Encrypt)
- **Domains**: `retromonkey.ddns.net` (No-IP DDNS, active), `retromonkey.com.au` (pending DNS)
- **DB on server**: Wipe and re-seed with `rm retro_store.db && sudo systemctl restart retrozone`

### Australian Compliance
- GST (10%) included in all prices: `gst_cents = amount_cents - int(amount_cents / 1.10)`
- BAS quarterly reporting via `/admin/accounting/bas`
- ABN stored in config, displayed in footer and invoices

## Key Gotchas

- **Windows subprocess**: `claude` is a `.cmd` wrapper — requires `shell=True`. `CREATE_NEW_PROCESS_GROUP` needed to kill child processes on timeout.
- **Paths**: use forward slashes in Python. `BASE_DIR` is the retro-store root.
- **Tkinter threading**: never touch widgets from worker threads — always use `app.after(0, ...)`.
- **MCP server cwd**: `.mcp.json` sets `"cwd": "."` — must run Claude from the retro-store directory.
- **Scraper blocking**: eBay/Alibaba block direct httpx scraping (403). Scrapers fall back through web-reader → SearXNG.
- **Budget tracking**: per-call via `--max-budget-usd`. Session accumulation in StatusBar.
- **No test suite**: workflows tested manually via GUI or MockApp harness.
- **SQLite FK constraints**: `inventory_batches.product_slug` references `products.slug` — batch seed data must match product slugs exactly.
- **Seed idempotency**: `seed_*()` functions check `count > 0` before inserting — safe to call on every app startup.
- **Product images**: WebP format. Product image paths stored in DB as `/static/images/<filename>.webp`.
