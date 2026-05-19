"""Supplier tracker MCP tools — CRUD for suppliers and supplier orders."""
from ..db.schema import get_conn
from datetime import datetime


def add_supplier(name: str, url: str = "", contact_email: str = "",
                 category: str = "", rating: int = 0, notes: str = "") -> str:
    """Add a new supplier to track. Returns confirmation with supplier ID.

    Use this when you find a good supplier on Alibaba or elsewhere and want to save their info.
    """
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO suppliers (name, url, contact_email, category, rating, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, url, contact_email, category, rating, notes)
        )
        conn.commit()
        sid = cursor.lastrowid
        return f"Supplier added: #{sid} — {name}\nCategory: {category}\nContact: {contact_email or 'N/A'}\nURL: {url or 'N/A'}"
    except Exception as e:
        return f"Error adding supplier: {e}"
    finally:
        conn.close()


def list_suppliers(category: str = "") -> str:
    """List tracked suppliers, optionally filtered by category.

    Returns all supplier details including contact info and notes.
    """
    conn = get_conn()
    try:
        if category:
            rows = conn.execute(
                "SELECT * FROM suppliers WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()

        if not rows:
            return f"No suppliers found{f' in category {category}' if category else ''}."

        lines = [f"Tracked Suppliers ({len(rows)}):\n"]
        for s in rows:
            stars = "*" * (s["rating"] or 0) if s["rating"] else "N/A"
            lines.append(
                f"#{s['id']} {s['name']} [{s['category'] or 'uncategorized'}]\n"
                f"   Rating: {stars} | Contact: {s['contact_email'] or 'N/A'}\n"
                f"   URL: {s['url'] or 'N/A'}\n"
                f"   Notes: {s['notes'] or 'N/A'} | Added: {s['created_at'][:10]}"
            )
        return "\n\n".join(lines)
    finally:
        conn.close()


def log_supplier_order(supplier_id: int, product_slug: str, units: int,
                       cost_per_unit_cents: int, status: str = "pending",
                       expected_arrival: str = "", notes: str = "") -> str:
    """Log a supplier order. Tracks cost, units, and delivery status.

    Status options: pending, ordered, shipped, received, cancelled
    """
    total = units * cost_per_unit_cents
    ordered_at = datetime.utcnow().isoformat() if status != "pending" else ""

    conn = get_conn()
    try:
        # Verify supplier exists
        sup = conn.execute("SELECT name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not sup:
            return f"Error: Supplier #{supplier_id} not found."

        cursor = conn.execute(
            "INSERT INTO supplier_orders "
            "(supplier_id, product_slug, units, cost_per_unit_cents, total_cost_cents, "
            "status, ordered_at, expected_arrival, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (supplier_id, product_slug, units, cost_per_unit_cents, total,
             status, ordered_at, expected_arrival, notes)
        )
        conn.commit()
        oid = cursor.lastrowid
        return (
            f"Order logged: #{oid}\n"
            f"Supplier: {sup['name']} (#{supplier_id})\n"
            f"Product: {product_slug} x{units}\n"
            f"Cost: ${cost_per_unit_cents/100:.2f}/unit = ${total/100:.2f} total\n"
            f"Status: {status}\n"
            f"Expected arrival: {expected_arrival or 'TBD'}"
        )
    except Exception as e:
        return f"Error logging order: {e}"
    finally:
        conn.close()


def get_supplier_orders(status: str = "") -> str:
    """View supplier orders, optionally filtered by status.

    Status options: pending, ordered, shipped, received, cancelled
    """
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT o.*, s.name as supplier_name "
                "FROM supplier_orders o JOIN suppliers s ON o.supplier_id = s.id "
                "WHERE o.status = ? ORDER BY o.created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT o.*, s.name as supplier_name "
                "FROM supplier_orders o JOIN suppliers s ON o.supplier_id = s.id "
                "ORDER BY o.created_at DESC"
            ).fetchall()

        if not rows:
            return f"No supplier orders found{f' with status {status}' if status else ''}."

        total_cost = sum(r["total_cost_cents"] for r in rows)
        lines = [f"Supplier Orders ({len(rows)}) — Total: ${total_cost/100:.2f}:\n"]

        for o in rows:
            lines.append(
                f"#{o['id']} {o['supplier_name']} → {o['product_slug']} x{o['units']}\n"
                f"   Cost: ${o['cost_per_unit_cents']/100:.2f}/unit = ${o['total_cost_cents']/100:.2f}\n"
                f"   Status: {o['status']} | Ordered: {o['ordered_at'][:10] if o['ordered_at'] else 'N/A'}\n"
                f"   Expected: {o['expected_arrival'] or 'TBD'} | Tracking: {o['tracking'] or 'N/A'}\n"
                f"   Notes: {o['notes'] or 'N/A'}"
            )
        return "\n\n".join(lines)
    finally:
        conn.close()
