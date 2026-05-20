"""StoreDB — all DB queries the GUI needs. Direct SQLite WAL access."""
import sqlite3
import json
from datetime import datetime, timedelta
from . import config


class StoreDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Dashboard stats ──

    def get_order_count(self):
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()
        return count

    def get_order_count_by_status(self, status):
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM orders WHERE status = ?", (status,)).fetchone()[0]
        conn.close()
        return count

    def get_total_revenue_cents(self):
        conn = self._conn()
        total = conn.execute(
            "SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE status IN ('paid', 'shipped', 'completed')"
        ).fetchone()[0]
        conn.close()
        return total

    def get_recent_orders(self, limit=10):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_open_ticket_count(self):
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress')").fetchone()[0]
        conn.close()
        return count

    def get_product_count(self):
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        conn.close()
        return count

    # ── Orders ──

    def get_orders(self, status=None, limit=100):
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_orders_since(self, hours=24):
        conn = self._conn()
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_order(self, order_id):
        conn = self._conn()
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_order_status(self, order_id, status):
        conn = self._conn()
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), order_id)
        )
        conn.commit()
        conn.close()

    def update_order_tracking(self, order_id, tracking):
        conn = self._conn()
        conn.execute(
            "UPDATE orders SET tracking = ?, updated_at = ? WHERE id = ?",
            (tracking, datetime.utcnow().isoformat(), order_id)
        )
        conn.commit()
        conn.close()

    # ── Products ──

    def get_products(self, category=None):
        conn = self._conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM products WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_product(self, slug):
        conn = self._conn()
        row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── Batches ──

    def get_batches(self, status=None):
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT b.*, p.name as product_name, p.price_cents as retail_price_cents "
                "FROM inventory_batches b JOIN products p ON b.product_slug = p.slug "
                "WHERE b.status = ? ORDER BY b.created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT b.*, p.name as product_name, p.price_cents as retail_price_cents "
                "FROM inventory_batches b JOIN products p ON b.product_slug = p.slug "
                "ORDER BY b.created_at DESC"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_active_batches(self):
        return self.get_batches(status="active")

    def update_batch_status(self, batch_id, status):
        conn = self._conn()
        conn.execute("UPDATE inventory_batches SET status = ? WHERE id = ?", (status, batch_id))
        conn.commit()
        conn.close()

    def create_batch(self, product_slug, units_total, cost_per_unit_cents,
                     ordered_at, arrives_at, expires_at):
        conn = self._conn()
        conn.execute(
            "INSERT INTO inventory_batches "
            "(product_slug, units_total, units_sold, cost_per_unit_cents, "
            "ordered_at, arrives_at, expires_at, status) "
            "VALUES (?, ?, 0, ?, ?, ?, ?, 'active')",
            (product_slug, units_total, cost_per_unit_cents,
             ordered_at, arrives_at, expires_at)
        )
        conn.commit()
        conn.close()

    # ── Tickets ──

    def get_tickets(self, status=None, limit=50):
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tickets ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_ticket(self, ticket_key):
        conn = self._conn()
        row = conn.execute("SELECT * FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_ticket_status(self, ticket_key, status):
        conn = self._conn()
        conn.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_key = ?",
            (status, datetime.utcnow().isoformat(), ticket_key)
        )
        conn.commit()
        conn.close()

    def add_ticket_message(self, ticket_key, message, is_admin=1):
        conn = self._conn()
        ticket = conn.execute("SELECT messages_json FROM tickets WHERE ticket_key = ?",
                              (ticket_key,)).fetchone()
        if ticket:
            messages = json.loads(ticket["messages_json"])
            messages.append({
                "from": "admin" if is_admin else "customer",
                "text": message,
                "time": datetime.utcnow().isoformat()
            })
            conn.execute(
                "UPDATE tickets SET messages_json = ?, updated_at = ? WHERE ticket_key = ?",
                (json.dumps(messages), datetime.utcnow().isoformat(), ticket_key)
            )
            conn.commit()
        conn.close()

    # ── Analytics ──

    def get_sales_velocity(self, days=30):
        """Units sold per product in last N days."""
        conn = self._conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = conn.execute("""
            SELECT p.slug, p.name, p.stock, p.price_cents,
                   COUNT(oi.order_id) as units_sold,
                   SUM(oi.qty) as total_qty
            FROM products p
            LEFT JOIN (
                SELECT o.id as order_id, json_each.value as item_json
                FROM orders o, json_each(o.items_json)
                WHERE o.status IN ('paid', 'shipped', 'completed')
                AND o.created_at >= ?
            ) oi ON json_extract(oi.item_json, '$.slug') = p.slug
            GROUP BY p.slug
            ORDER BY total_qty DESC
        """, (cutoff,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Suppliers ──

    def get_suppliers(self, category=None):
        conn = self._conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM suppliers WHERE category = ? ORDER BY name", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_supplier(self, supplier_id):
        conn = self._conn()
        row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create_supplier(self, name, url="", contact_email="", category="", rating=0, notes=""):
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO suppliers (name, url, contact_email, category, rating, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, url, contact_email, category, rating, notes)
        )
        conn.commit()
        supplier_id = cursor.lastrowid
        conn.close()
        return supplier_id

    def update_supplier(self, supplier_id, **fields):
        conn = self._conn()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [supplier_id]
        conn.execute(f"UPDATE suppliers SET {sets} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def delete_supplier(self, supplier_id):
        conn = self._conn()
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()
        conn.close()

    # ── Workflow Runs ──

    def save_workflow_run(self, workflow_name, steps, step_states, step_results, report, error, state):
        conn = self._conn()
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO workflow_runs "
            "(workflow_name, steps_json, step_states_json, step_results_json, report, error, state, started_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (workflow_name, json.dumps(steps), json.dumps(step_states),
             json.dumps(step_results), report, error, state, now, now if state == "completed" else None)
        )
        conn.commit()
        conn.close()

    def get_workflow_runs(self, limit=50):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_workflow_run(self, run_id):
        conn = self._conn()
        row = conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── Activity Log ──

    def log_activity(self, action, target_type="", target_id="", details=""):
        conn = self._conn()
        conn.execute(
            "INSERT INTO admin_activity_log (action, target_type, target_id, details) "
            "VALUES (?, ?, ?, ?)",
            (action, target_type, str(target_id), details)
        )
        conn.commit()
        conn.close()

    def get_activity_log(self, limit=100):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM admin_activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Batch Expiry ──

    def check_batch_expiry(self):
        """Find active batches past their expires_at and mark them expired. Returns count."""
        conn = self._conn()
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "UPDATE inventory_batches SET status = 'expired' "
            "WHERE status = 'active' AND expires_at < ?",
            (now,)
        )
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    # ── Chat Sessions ──

    def create_chat_session(self, title=""):
        conn = self._conn()
        cursor = conn.execute("INSERT INTO chat_sessions (title) VALUES (?)", (title,))
        conn.commit()
        sid = cursor.lastrowid
        conn.close()
        return sid

    def save_chat_message(self, session_id, role, text):
        conn = self._conn()
        conn.execute(
            "INSERT INTO chat_messages_store (session_id, role, text) VALUES (?, ?, ?)",
            (session_id, role, text)
        )
        conn.commit()
        conn.close()

    def get_chat_sessions(self, limit=20):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_chat_messages(self, session_id):
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM chat_messages_store WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_session_id(self):
        conn = self._conn()
        row = conn.execute(
            "SELECT id FROM chat_sessions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row["id"] if row else None

    # ── Analytics ──

    def get_store_state_summary(self):
        """Compact text summary for Claude context."""
        conn = self._conn()
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]
        paid = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid'").fetchone()[0]
        shipped = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'shipped'").fetchone()[0]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE status IN ('paid','shipped','completed')"
        ).fetchone()[0]
        open_tickets = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('open','in_progress')"
        ).fetchone()[0]
        active_batches = conn.execute(
            "SELECT COUNT(*) FROM inventory_batches WHERE status = 'active'"
        ).fetchone()[0]

        # Recent orders (last 24h)
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        recent = conn.execute(
            "SELECT id, email, total_cents, status, created_at FROM orders WHERE created_at >= ?",
            (cutoff,)
        ).fetchall()
        recent_text = "\n".join(
            f"  #{r['id']}: {r['email']} ${r['total_cents']/100:.2f} [{r['status']}] {r['created_at']}"
            for r in recent
        ) or "  (none)"

        conn.close()

        return f"""Store State (live):
- Total orders: {total_orders} (pending: {pending}, paid: {paid}, shipped: {shipped})
- Revenue: ${revenue/100:.2f}
- Open tickets: {open_tickets}
- Active batches: {active_batches}
- Recent orders (24h):
{recent_text}"""

    # ── AI Decision Memory ──

    def log_ai_decision(self, decision_type, product_slug, decision,
                        reasoning="", data_used="", confidence="medium"):
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO ai_decisions (decision_type, product_slug, decision, "
            "reasoning, data_used, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            (decision_type, product_slug, decision, reasoning, data_used, confidence)
        )
        conn.commit()
        decision_id = cursor.lastrowid
        conn.close()
        return decision_id

    def update_ai_decision_outcome(self, decision_id, outcome):
        conn = self._conn()
        conn.execute(
            "UPDATE ai_decisions SET outcome = ? WHERE id = ?",
            (outcome, decision_id)
        )
        conn.commit()
        conn.close()

    def get_ai_decisions(self, product_slug=None, decision_type=None, limit=50):
        conn = self._conn()
        query = "SELECT * FROM ai_decisions WHERE 1=1"
        params = []
        if product_slug:
            query += " AND product_slug = ?"
            params.append(product_slug)
        if decision_type:
            query += " AND decision_type = ?"
            params.append(decision_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_ai_note(self, category, subject, body, related_slug="", importance="normal"):
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO ai_notes (category, subject, body, related_slug, importance) "
            "VALUES (?, ?, ?, ?, ?)",
            (category, subject, body, related_slug, importance)
        )
        note_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO ai_notes_fts (note_id, subject, body) VALUES (?, ?, ?)",
            (note_id, subject, body)
        )
        conn.commit()
        conn.close()
        return note_id

    def update_ai_note(self, note_id, **fields):
        conn = self._conn()
        if "subject" in fields or "body" in fields:
            # Update FTS index
            note = conn.execute("SELECT subject, body FROM ai_notes WHERE id = ?", (note_id,)).fetchone()
            if note:
                subj = fields.get("subject", note["subject"])
                body = fields.get("body", note["body"])
                conn.execute("DELETE FROM ai_notes_fts WHERE note_id = ?", (note_id,))
                conn.execute("INSERT INTO ai_notes_fts (note_id, subject, body) VALUES (?, ?, ?)",
                           (note_id, subj, body))
        fields["updated_at"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [note_id]
        conn.execute(f"UPDATE ai_notes SET {sets} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_ai_notes(self, category=None, limit=50):
        conn = self._conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM ai_notes WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ai_notes ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_ai_context_for_product(self, slug):
        """Get decisions + notes for a specific product — compact text for context."""
        conn = self._conn()
        decisions = conn.execute(
            "SELECT decision_type, decision, reasoning, outcome, confidence, created_at "
            "FROM ai_decisions WHERE product_slug = ? ORDER BY created_at DESC LIMIT 10",
            (slug,)
        ).fetchall()
        notes = conn.execute(
            "SELECT category, subject, body, importance FROM ai_notes "
            "WHERE related_slug = ? ORDER BY updated_at DESC LIMIT 10",
            (slug,)
        ).fetchall()
        conn.close()

        parts = []
        if decisions:
            parts.append(f"Recent decisions for {slug}:")
            for d in decisions:
                parts.append(f"  [{d['decision_type']}] {d['decision']} — {d['reasoning']} "
                           f"(outcome: {d['outcome'] or 'pending'}, confidence: {d['confidence']})")
        if notes:
            parts.append(f"Notes for {slug}:")
            for n in notes:
                parts.append(f"  [{n['category']}] {n['subject']}: {n['body']} ({n['importance']})")
        return "\n".join(parts) if parts else ""

    def get_recent_ai_summary(self, days=7):
        """Compact text summary of recent AI activity for system prompt injection."""
        conn = self._conn()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        decisions = conn.execute(
            "SELECT decision_type, product_slug, decision, reasoning, outcome, confidence "
            "FROM ai_decisions WHERE created_at >= ? ORDER BY created_at DESC LIMIT 20",
            (cutoff,)
        ).fetchall()

        notes = conn.execute(
            "SELECT category, subject, body, related_slug "
            "FROM ai_notes WHERE created_at >= ? ORDER BY created_at DESC LIMIT 10",
            (cutoff,)
        ).fetchall()
        conn.close()

        parts = []
        if decisions:
            parts.append(f"Recent AI Decisions (last {days}d):")
            for d in decisions:
                slug = d['product_slug'] or 'general'
                parts.append(f"  [{d['decision_type']}] {slug}: {d['decision']} "
                           f"— outcome: {d['outcome'] or 'pending'}")
        if notes:
            parts.append(f"Recent AI Notes (last {days}d):")
            for n in notes:
                parts.append(f"  [{n['category']}] {n['subject']}: {n['body'][:100]}")

        return "\n".join(parts) if parts else "(No recent AI activity)"
