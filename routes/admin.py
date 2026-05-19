"""Admin panel routes."""
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db, get_active_batch, get_batch_price, get_batch_phase, get_batch_remaining
import config
from app import limiter
import stripe

log = logging.getLogger("retromonkey.admin")

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
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        stored = config.ADMIN_PASSWORD

        # Support both hashed and plain-text passwords
        if stored.startswith("pbkdf2:") or stored.startswith("sha256:"):
            matched = check_password_hash(stored, pw)
        else:
            matched = pw == stored

        if matched:
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
        "gst_collected": conn.execute("SELECT COALESCE(SUM(gst_cents), 0) FROM orders WHERE status = 'paid'").fetchone()[0],
        "pending_orders": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0],
        "open_tickets": conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "kb_articles": conn.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0],
    }

    # COGS: total cost of goods sold from batches
    stats["cogs"] = conn.execute("""
        SELECT COALESCE(SUM(units_sold * cost_per_unit_cents), 0)
        FROM inventory_batches
    """).fetchone()[0]
    stats["gross_profit"] = stats["revenue"] - stats["cogs"]
    stats["margin_pct"] = round(stats["gross_profit"] / stats["revenue"] * 100, 1) if stats["revenue"] else 0

    recent_orders = conn.execute("""
        SELECT * FROM orders ORDER BY created_at DESC LIMIT 10
    """).fetchall()
    open_tickets = conn.execute("""
        SELECT * FROM tickets WHERE status != 'closed' ORDER BY created_at DESC LIMIT 10
    """).fetchall()

    # Low stock alerts (products with stock <= 5)
    low_stock = conn.execute("""
        SELECT * FROM products WHERE stock > 0 AND stock <= 5 ORDER BY stock ASC
    """).fetchall()

    conn.close()
    return render_template("admin/dashboard.html", stats=stats,
                         recent_orders=recent_orders, open_tickets=open_tickets,
                         low_stock=low_stock)


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
    # Ensure GST field exists
    if "gst_cents" not in order:
        order["gst_cents"] = 0

    # COGS per order: look up cost from active batch at time of sale
    order["cogs_cents"] = 0
    for item in order["items"]:
        slug = item.get("slug", "")
        qty = item.get("qty", 0)
        batch = conn.execute(
            "SELECT cost_per_unit_cents FROM inventory_batches WHERE product_slug = ? AND status = 'active' LIMIT 1",
            (slug,)
        ).fetchone()
        cost = batch["cost_per_unit_cents"] if batch else 0
        item["cost_per_unit_cents"] = cost
        item["line_cogs"] = cost * qty
        order["cogs_cents"] += item["line_cogs"]
    order["profit_cents"] = order["total_cents"] - order["cogs_cents"]
    order["margin_pct"] = round(order["profit_cents"] / order["total_cents"] * 100, 1) if order["total_cents"] else 0

    conn.close()
    return render_template("admin/order_detail.html", order=order, abn=config.ABN, business_name=config.BUSINESS_NAME)


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


# ── Products CRUD ──

@admin_bp.route("/products")
@admin_required
def products():
    conn = get_db()
    category = request.args.get("category", "")
    if category:
        rows = conn.execute("SELECT * FROM products WHERE category = ? ORDER BY name", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    categories = conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    low_stock = conn.execute("SELECT * FROM products WHERE stock > 0 AND stock <= 5 ORDER BY stock ASC").fetchall()
    conn.close()
    return render_template("admin/products.html", products=rows, categories=categories,
                         category_filter=category, low_stock=low_stock)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    if request.method == "POST":
        slug = request.form.get("slug", "").strip()
        name = request.form.get("name", "").strip()
        tagline = request.form.get("tagline", "").strip()
        description = request.form.get("description", "").strip()
        price_cents = request.form.get("price_cents", type=int)
        compare_price_cents = request.form.get("compare_price_cents", 0, type=int) or 0
        stock = request.form.get("stock", 0, type=int)
        category = request.form.get("category", "handhelds")
        featured = 1 if request.form.get("featured") else 0
        badge = request.form.get("badge", "").strip()
        image = request.form.get("image", "").strip()

        if not all([slug, name, price_cents]):
            flash("Slug, name, and price are required.", "error")
        else:
            conn = get_db()
            try:
                conn.execute("""
                    INSERT INTO products (slug, name, tagline, description, price_cents,
                        compare_price_cents, image, gallery, specs, stock, featured, category, badge)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '[]', '{}', ?, ?, ?, ?)
                """, (slug, name, tagline, description, price_cents,
                      compare_price_cents, image, stock, featured, category, badge))
                conn.commit()
                flash(f"Product '{name}' created.", "success")
                return redirect(url_for("admin.products"))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                conn.close()

    return render_template("admin/product_form.html", product=None)


@admin_bp.route("/products/<slug>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(slug):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    if not product:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("admin.products"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        tagline = request.form.get("tagline", "").strip()
        description = request.form.get("description", "").strip()
        price_cents = request.form.get("price_cents", type=int)
        compare_price_cents = request.form.get("compare_price_cents", 0, type=int) or 0
        stock = request.form.get("stock", 0, type=int)
        category = request.form.get("category", "handhelds")
        featured = 1 if request.form.get("featured") else 0
        badge = request.form.get("badge", "").strip()
        image = request.form.get("image", "").strip()

        conn.execute("""
            UPDATE products SET name=?, tagline=?, description=?, price_cents=?,
                compare_price_cents=?, stock=?, category=?, featured=?, badge=?, image=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE slug=?
        """, (name, tagline, description, price_cents, compare_price_cents,
              stock, category, featured, badge, image, slug))
        conn.commit()
        conn.close()
        flash(f"Product '{name}' updated.", "success")
        return redirect(url_for("admin.products"))

    product = dict(product)
    conn.close()
    return render_template("admin/product_form.html", product=product)


@admin_bp.route("/products/<slug>/delete", methods=["POST"])
@admin_required
def product_delete(slug):
    conn = get_db()
    product = conn.execute("SELECT name FROM products WHERE slug = ?", (slug,)).fetchone()
    if not product:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("admin.products"))

    # Check for active batches or orders referencing this product
    active_batches = conn.execute(
        "SELECT COUNT(*) FROM inventory_batches WHERE product_slug = ? AND status = 'active'", (slug,)
    ).fetchone()[0]
    if active_batches > 0:
        conn.close()
        flash(f"Cannot delete '{product['name']}' — it has {active_batches} active batch(es). Deactivate batches first.", "error")
        return redirect(url_for("admin.products"))

    conn.execute("DELETE FROM products WHERE slug = ?", (slug,))
    conn.commit()
    conn.close()
    flash(f"Product '{product['name']}' deleted.", "success")
    return redirect(url_for("admin.products"))


# ── P&L Reporting ──

@admin_bp.route("/pnl")
@admin_required
def pnl():
    conn = get_db()
    days = request.args.get("days", 30, type=int)

    # Overall P&L
    overall = conn.execute("""
        SELECT
            COUNT(*) as order_count,
            COALESCE(SUM(total_cents), 0) as revenue,
            COALESCE(SUM(gst_cents), 0) as gst,
            COALESCE(SUM(shipping_cents), 0) as shipping_revenue
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= datetime('now', ? || ' days')
    """, (-days,)).fetchone()

    # Per-batch P&L
    batch_pnl = conn.execute("""
        SELECT
            b.id, b.product_slug, p.name as product_name,
            b.units_total, b.units_sold,
            b.cost_per_unit_cents,
            b.cost_per_unit_cents * b.units_sold as total_cost,
            b.status,
            b.arrives_at, b.expires_at
        FROM inventory_batches b
        JOIN products p ON p.slug = b.product_slug
        WHERE b.units_sold > 0
        ORDER BY b.units_sold DESC
    """).fetchall()

    # Calculate revenue per batch from order items
    batch_list = []
    for b in batch_pnl:
        b = dict(b)
        # Estimate revenue from batch pricing
        batch = conn.execute("SELECT * FROM inventory_batches WHERE id = ?", (b["id"],)).fetchone()
        if batch:
            batch = dict(batch)
            if batch["status"] == "active":
                price = get_batch_price(batch)
            else:
                price = int(batch["cost_per_unit_cents"] * 1.40)  # assume instock price
            b["revenue_cents"] = price * b["units_sold"]
        else:
            b["revenue_cents"] = 0
        b["profit_cents"] = b["revenue_cents"] - b["total_cost"]
        b["margin_pct"] = round(b["profit_cents"] / b["revenue_cents"] * 100, 1) if b["revenue_cents"] else 0
        batch_list.append(b)

    total_cogs = sum(b["total_cost"] for b in batch_list)
    total_rev = sum(b["revenue_cents"] for b in batch_list)
    total_profit = total_rev - total_cogs
    total_margin = round(total_profit / total_rev * 100, 1) if total_rev else 0

    # Daily revenue chart (last 14 days)
    daily = conn.execute("""
        SELECT
            date(created_at) as day,
            COUNT(*) as orders,
            COALESCE(SUM(total_cents), 0) as revenue
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= datetime('now', '-14 days')
        GROUP BY date(created_at)
        ORDER BY day
    """).fetchall()

    conn.close()

    return render_template("admin/pnl.html",
                         overall=dict(overall),
                         batches=batch_list,
                         total_cogs=total_cogs,
                         total_rev=total_rev,
                         total_profit=total_profit,
                         total_margin=total_margin,
                         daily=daily,
                         days=days)


# ── Refunds ──

@admin_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@admin_required
def order_refund(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        flash("Order not found.", "error")
        return redirect(url_for("admin.orders"))

    refund_type = request.form.get("refund_type", "full")
    amount_cents = request.form.get("amount_cents", type=int)
    reason = request.form.get("reason", "requested_by_customer")

    if refund_type == "full":
        amount = order["total_cents"]
    elif refund_type == "partial" and amount_cents and amount_cents > 0:
        amount = min(amount_cents, order["total_cents"])
    else:
        conn.close()
        flash("Invalid refund parameters.", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    payment_intent = order["stripe_payment_intent"]
    if not payment_intent:
        conn.close()
        flash("No payment intent found for this order.", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    try:
        refund_obj = stripe.Refund.create(
            payment_intent=payment_intent,
            amount=amount if refund_type == "partial" else None,
            reason=reason,
        )
        # Update order
        new_status = "refunded" if refund_type == "full" else order["status"]
        refund_total = order.get("refund_cents", 0) + amount
        conn.execute("""
            UPDATE orders SET status = ?, refund_cents = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, refund_total, order_id))
        conn.commit()
        conn.close()

        flash(f"{'Full' if refund_type == 'full' else 'Partial'} refund of ${amount / 100:.2f} processed.", "success")
        log.info("Refund processed: order #%s, amount=%d, type=%s", order_id, amount, refund_type)
    except stripe.error.StripeError as e:
        conn.close()
        flash(f"Stripe error: {e}", "error")
        log.error("Refund failed: order #%s, error=%s", order_id, e)

    return redirect(url_for("admin.order_detail", order_id=order_id))
