"""Admin panel routes."""
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db, get_active_batch, get_batch_price, get_batch_phase, get_batch_remaining
import config

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator to require admin login."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Admin login required.", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == config.ADMIN_PASSWORD:
            session["admin"] = True
            flash("Logged in.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Wrong password.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("store.index"))


@admin_bp.route("/")
@admin_required
def dashboard():
    conn = get_db()
    stats = {
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "revenue": conn.execute("SELECT COALESCE(SUM(total_cents), 0) FROM orders WHERE status = 'paid'").fetchone()[0],
        "pending_orders": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0],
        "open_tickets": conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "kb_articles": conn.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0],
    }
    recent_orders = conn.execute("""
        SELECT * FROM orders ORDER BY created_at DESC LIMIT 10
    """).fetchall()
    open_tickets = conn.execute("""
        SELECT * FROM tickets WHERE status != 'closed' ORDER BY created_at DESC LIMIT 10
    """).fetchall()
    conn.close()
    return render_template("admin/dashboard.html", stats=stats,
                         recent_orders=recent_orders, open_tickets=open_tickets)


@admin_bp.route("/orders")
@admin_required
def orders():
    conn = get_db()
    status_filter = request.args.get("status", "")
    if status_filter:
        orders = conn.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status_filter,)).fetchall()
    else:
        orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/orders.html", orders=orders, status_filter=status_filter)


@admin_bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def order_detail(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))

    if request.method == "POST":
        status = request.form.get("status", order["status"])
        tracking = request.form.get("tracking", order["tracking"])
        conn.execute("UPDATE orders SET status = ?, tracking = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, tracking, order_id))
        conn.commit()
        flash("Order updated.", "success")
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    order = dict(order)
    order["items"] = json.loads(order["items_json"])
    order["address"] = json.loads(order.get("address", "{}")) if order.get("address") else {}
    conn.close()
    return render_template("admin/order_detail.html", order=order)


@admin_bp.route("/tickets")
@admin_required
def tickets():
    conn = get_db()
    status_filter = request.args.get("status", "")
    if status_filter:
        tickets = conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC", (status_filter,)).fetchall()
    else:
        tickets = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("admin/tickets.html", tickets=tickets, status_filter=status_filter)


@admin_bp.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
@admin_required
def ticket_detail(ticket_id):
    conn = get_db()
    ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        flash("Ticket not found.", "error")
        return redirect(url_for("admin.tickets"))

    if request.method == "POST":
        action = request.form.get("action", "reply")
        if action == "reply":
            reply_text = request.form.get("reply", "").strip()
            if reply_text:
                ticket = dict(ticket)
                messages = json.loads(ticket["messages_json"])
                from datetime import datetime
                messages.append({"from": "admin", "text": reply_text, "time": datetime.utcnow().isoformat()})
                conn.execute("UPDATE tickets SET messages_json = ?, status = 'answered', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                           (json.dumps(messages), ticket_id))
                conn.commit()
                flash("Reply sent.", "success")
        elif action in ("open", "closed", "answered"):
            conn.execute("UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (action, ticket_id))
            conn.commit()
            flash(f"Ticket status set to {action}.", "success")

        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()

    ticket = dict(ticket)
    ticket["messages"] = json.loads(ticket["messages_json"])
    conn.close()
    return render_template("admin/ticket_detail.html", ticket=ticket)


# ── Inventory Batches ──

@admin_bp.route("/batches")
@admin_required
def batches():
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, p.name as product_name
        FROM inventory_batches b
        JOIN products p ON p.slug = b.product_slug
        ORDER BY b.status = 'active' DESC, b.id DESC
    """).fetchall()
    conn.close()

    batch_list = []
    for b in rows:
        b = dict(b)
        if b['status'] == 'active':
            b['current_price_cents'] = get_batch_price(b)
            b['phase'] = get_batch_phase(b)
            b['remaining'] = get_batch_remaining(b)
        else:
            b['current_price_cents'] = 0
            b['phase'] = b['status']
            b['remaining'] = 0
        # P&L
        sold = b['units_sold']
        cost = b['cost_per_unit_cents']
        revenue = b.get('current_price_cents', 0) * sold if b['status'] == 'active' else 0
        b['revenue_cents'] = revenue
        b['cost_of_goods_cents'] = cost * sold
        b['profit_cents'] = revenue - (cost * sold)
        batch_list.append(b)

    return render_template("admin/batches.html", batches=batch_list)


@admin_bp.route("/batches/new", methods=["GET", "POST"])
@admin_required
def batch_new():
    if request.method == "POST":
        product_slug = request.form.get("product_slug", "").strip()
        units_total = request.form.get("units_total", type=int)
        cost_per_unit_cents = request.form.get("cost_per_unit_cents", type=int)
        arrives_at = request.form.get("arrives_at", "").strip()
        expires_at = request.form.get("expires_at", "").strip()

        if not all([product_slug, units_total, cost_per_unit_cents, arrives_at, expires_at]):
            flash("All fields are required.", "error")
        else:
            conn = get_db()
            conn.execute("""
                INSERT INTO inventory_batches (product_slug, units_total, units_sold, cost_per_unit_cents,
                    ordered_at, arrives_at, expires_at, status)
                VALUES (?, ?, 0, ?, ?, ?, ?, 'active')
            """, (product_slug, units_total, cost_per_unit_cents,
                  datetime.utcnow().isoformat(), arrives_at, expires_at))
            conn.commit()
            conn.close()
            flash(f"Batch created for {product_slug}.", "success")
            return redirect(url_for("admin.batches"))

    conn = get_db()
    products = conn.execute("SELECT slug, name FROM products ORDER BY name").fetchall()
    conn.close()
    return render_template("admin/batch_form.html", products=products, batch=None)


@admin_bp.route("/batches/<int:batch_id>", methods=["GET", "POST"])
@admin_required
def batch_detail(batch_id):
    conn = get_db()
    batch = conn.execute("""
        SELECT b.*, p.name as product_name
        FROM inventory_batches b
        JOIN products p ON p.slug = b.product_slug
        WHERE b.id = ?
    """, (batch_id,)).fetchone()
    if not batch:
        conn.close()
        flash("Batch not found.", "error")
        return redirect(url_for("admin.batches"))

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "deactivate":
            conn.execute("UPDATE inventory_batches SET status = 'expired' WHERE id = ?", (batch_id,))
            conn.commit()
            flash("Batch deactivated.", "success")
        elif action == "reactivate":
            conn.execute("UPDATE inventory_batches SET status = 'active' WHERE id = ?", (batch_id,))
            conn.commit()
            flash("Batch reactivated.", "success")

    batch = dict(batch)
    if batch['status'] == 'active':
        batch['current_price_cents'] = get_batch_price(batch)
        batch['phase'] = get_batch_phase(batch)
        batch['remaining'] = get_batch_remaining(batch)
        batch['preorder_price'] = int(batch['cost_per_unit_cents'] * 1.10)
        batch['instock_price'] = int(batch['cost_per_unit_cents'] * 1.40)
        batch['clearance_price'] = batch['cost_per_unit_cents']
    else:
        batch['current_price_cents'] = 0
        batch['phase'] = batch['status']
        batch['remaining'] = 0

    conn.close()
    return render_template("admin/batch_detail.html", batch=batch)
