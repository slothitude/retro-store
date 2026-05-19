"""DB schema for retro-tools — suppliers, orders, email drafts, price checks."""
import sqlite3
import os

# Use the same DB as the main app
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "retro_store.db"
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    category TEXT DEFAULT '',
    rating INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    product_slug TEXT NOT NULL,
    units INTEGER NOT NULL,
    cost_per_unit_cents INTEGER NOT NULL,
    total_cost_cents INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    ordered_at TEXT,
    expected_arrival TEXT,
    tracking TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS email_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS price_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_slug TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    results_json TEXT NOT NULL DEFAULT '[]',
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_tables():
    """Create retro-tools tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Run on import
ensure_tables()
