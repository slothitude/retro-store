"""Store routes — products, cart, checkout."""
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import stripe
from db import get_db, get_active_batch, get_batch_price, get_batch_phase, get_batch_remaining
import config
from app import limiter

store_bp = Blueprint("store", __name__)
log = logging.getLogger(__name__)


def get_cart():
    """Get cart from session."""
    return session.get("cart", [])


def save_cart(cart):
    """Save cart to session."""
    session["cart"] = cart
    session.modified = True


def cart_total():
    """Calculate cart total in cents."""
    cart = get_cart()
    if not cart:
        return 0
    conn = get_db()
    total = 0
    for item in cart:
        product = conn.execute("SELECT price_cents, slug FROM products WHERE id = ?", (item["id"],)).fetchone()
        if product:
            price = product["price_cents"]
            batch = get_active_batch(product["slug"])
            if batch and get_batch_remaining(batch) > 0:
                price = get_batch_price(batch)
            total += price * item["qty"]
    conn.close()
    return total


def cart_item_count():
    return sum(item["qty"] for item in get_cart())


def calculate_gst(total_cents):
    """Calculate GST component from GST-inclusive total."""
    return round(total_cents - (total_cents / 1.10))


def send_order_confirmation(order):
    """Send order confirmation email (best effort, never blocks order flow)."""
    if not config.SMTP_HOST:
        log.info("SMTP not configured, skipping order confirmation email")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        items = json.loads(order["items_json"]) if isinstance(order["items_json"], str) else order["items_json"]
        gst_cents = calculate_gst(order["total_cents"])

        item_rows = ""
        for item in items:
            item_rows += f"<tr><td>{item.get('name', '')}</td><td>x{item.get('qty', 1)}</td><td>${item.get('price', 0) / 100:.2f}</td></tr>"

        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #6c5ce7;">Order Confirmed!</h1>
            <p>Thanks for your order, {order.get('name', 'valued customer')}!</p>
            <h2>Order #{order['id']}</h2>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background: #f0f0f0;"><th>Item</th><th>Qty</th><th>Price</th></tr>
                {item_rows}
            </table>
            <p><strong>Total (incl. GST):</strong> ${order['total_cents'] / 100:.2f}</p>
            <p><strong>GST:</strong> ${gst_cents / 100:.2f}</p>
            <hr>
            <p style="color: #888; font-size: 12px;">
                {config.BUSINESS_NAME} ABN: {config.ABN}<br>
                Prices include GST where applicable.
            </p>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"RetroZone Order #{order['id']} — Confirmed!"
        msg["From"] = config.SMTP_FROM
        msg["To"] = order["email"]
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASS)
            server.sendmail(config.SMTP_FROM, order["email"], msg.as_string())

        log.info("Order confirmation sent to %s for order #%s", order["email"], order["id"])
    except Exception:
        log.exception("Failed to send order confirmation email")


@store_bp.context_processor
def inject_cart():
    return {"cart_items": cart_item_count()}


def calculate_shipping(total_cents):
    """Tiered domestic shipping for Australia."""
    if total_cents >= 5000:
        return 0  # Free shipping over $50
    elif total_cents >= 3000:
        return 599   # $5.99
    else:
        return 899   # $8.99


@store_bp.route("/health")
def health_check():
    """Health check endpoint for monitoring."""
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "healthy", "db": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "db": "error", "error": str(e)}), 503


# ── Public pages ──

def _enrich_products(product_list):
    """Add batch pricing data to a list of product dicts."""
    for i, p in enumerate(product_list):
        p = dict(p)
        batch = get_active_batch(p['slug'])
        if batch and get_batch_remaining(batch) > 0:
            p['batch_price_cents'] = get_batch_price(batch)
            p['batch_phase'] = get_batch_phase(batch)
            p['batch_remaining'] = get_batch_remaining(batch)
            p['batch_cost_cents'] = batch['cost_per_unit_cents']
            p['batch_arrives_at'] = batch['arrives_at']
        product_list[i] = p
    return product_list


@store_bp.route("/")
def index():
    conn = get_db()
    featured = conn.execute(
        "SELECT * FROM products WHERE featured = 1 AND stock > 0 ORDER BY id"
    ).fetchall()
    all_products = conn.execute(
        "SELECT * FROM products WHERE stock > 0 ORDER BY category, name"
    ).fetchall()
    conn.close()

    featured = _enrich_products(list(featured))
    all_products = _enrich_products(list(all_products))

    return render_template("index.html", featured=featured, products=all_products)


@store_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("store.index"))

    conn = get_db()
    products = conn.execute(
        """SELECT * FROM products
           WHERE (name LIKE ? OR tagline LIKE ? OR category LIKE ? OR description LIKE ?)
           AND stock > 0
           ORDER BY featured DESC, name""",
        (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")
    ).fetchall()
    conn.close()

    products = _enrich_products(list(products))
    return render_template("search.html", products=products, query=q)


@store_bp.route("/product/<slug>")
def product(slug):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    if not product:
        conn.close()
        return render_template("404.html"), 404
    # Parse JSON fields
    product = dict(product)
    product["gallery"] = json.loads(product.get("gallery", "[]"))
    product["specs"] = json.loads(product.get("specs", "{}"))

    # Apply batch pricing
    batch = get_active_batch(slug)
    if batch:
        remaining = get_batch_remaining(batch)
        product['batch'] = batch
        product['batch_remaining'] = remaining
        if remaining > 0:
            product['batch_price_cents'] = get_batch_price(batch)
            product['batch_phase'] = get_batch_phase(batch)
            product['batch_cost_cents'] = batch['cost_per_unit_cents']
            # Override display price with batch price
            product['display_price_cents'] = product['batch_price_cents']
            product['display_compare_cents'] = int(batch['cost_per_unit_cents'] * 1.40)
            # Effective stock = min(product stock, batch remaining)
            product['effective_stock'] = min(product['stock'], remaining)
        else:
            product['batch_phase'] = 'soldout'
            product['effective_stock'] = 0
            product['display_price_cents'] = product['price_cents']
            product['display_compare_cents'] = product['compare_price_cents']
    else:
        product['display_price_cents'] = product['price_cents']
        product['display_compare_cents'] = product['compare_price_cents']
        product['effective_stock'] = product['stock']

    # GST calculation for display
    product['gst_cents'] = calculate_gst(product.get('display_price_cents', product['price_cents']))

    conn.close()
    return render_template("product.html", product=product)


# ── Cart ──

@store_bp.route("/cart")
def cart():
    cart = get_cart()
    conn = get_db()
    items = []
    total = 0
    for ci in cart:
        p = conn.execute("SELECT * FROM products WHERE id = ?", (ci["id"],)).fetchone()
        if p:
            p = dict(p)
            # Apply batch pricing
            batch = get_active_batch(p["slug"])
            if batch and get_batch_remaining(batch) > 0:
                p["price_cents"] = get_batch_price(batch)
            p["qty"] = ci["qty"]
            p["line_total"] = p["price_cents"] * ci["qty"]
            total += p["line_total"]
            items.append(p)
    conn.close()
    gst = calculate_gst(total) if total > 0 else 0
    shipping = calculate_shipping(total)
    return render_template("cart.html", items=items, total=total, gst=gst, shipping=shipping)


@store_bp.route("/cart/add", methods=["POST"])
@limiter.limit("30 per minute")
def cart_add():
    product_id = request.form.get("product_id", type=int)
    qty = request.form.get("qty", 1, type=int)
    if not product_id:
        flash("Invalid product.", "error")
        return redirect(url_for("store.index"))

    conn = get_db()
    product = conn.execute("SELECT id, name, stock FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("store.index"))

    cart = get_cart()
    # Find existing
    for item in cart:
        if item["id"] == product_id:
            item["qty"] = min(item["qty"] + qty, product["stock"])
            save_cart(cart)
            flash(f"Updated {product['name']} in cart.", "success")
            return redirect(url_for("store.cart"))

    cart.append({"id": product_id, "qty": min(qty, product["stock"])})
    save_cart(cart)
    flash(f"Added {product['name']} to cart.", "success")
    return redirect(url_for("store.cart"))


@store_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id):
    cart = get_cart()
    cart = [item for item in cart if item["id"] != product_id]
    save_cart(cart)
    flash("Item removed from cart.", "success")
    return redirect(url_for("store.cart"))


# ── Checkout ──

@store_bp.route("/checkout")
def checkout():
    cart = get_cart()
    if not cart:
        flash("Your cart is empty.", "error")
        return redirect(url_for("store.index"))

    conn = get_db()
    items = []
    total = 0
    for ci in cart:
        p = conn.execute("SELECT * FROM products WHERE id = ?", (ci["id"],)).fetchone()
        if p:
            p = dict(p)
            # Apply batch pricing
            batch = get_active_batch(p["slug"])
            if batch and get_batch_remaining(batch) > 0:
                p["price_cents"] = get_batch_price(batch)
            p["qty"] = ci["qty"]
            p["line_total"] = p["price_cents"] * ci["qty"]
            total += p["line_total"]
            items.append(p)
    conn.close()

    # Shipping calculation
    shipping = calculate_shipping(total)
    gst = calculate_gst(total + shipping) if total > 0 else 0

    return render_template("checkout.html", items=items, total=total, shipping=shipping,
                         gst=gst, stripe_key=config.STRIPE_PUBLIC_KEY)


@store_bp.route("/create-checkout-session", methods=["POST"])
@limiter.limit("10 per minute")
def create_checkout_session():
    cart = get_cart()
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    conn = get_db()
    line_items = []
    items_json = []

    for ci in cart:
        p = conn.execute("SELECT * FROM products WHERE id = ?", (ci["id"],)).fetchone()
        if not p:
            continue
        # Apply batch pricing
        price = p["price_cents"]
        batch = get_active_batch(p["slug"])
        if batch and get_batch_remaining(batch) > 0:
            price = get_batch_price(batch)

        # Stock validation — prevent overselling
        if p["stock"] < ci["qty"]:
            conn.close()
            return jsonify({"error": f"Not enough stock for {p['name']}"}), 400

        line_items.append({
            "price_data": {
                "currency": config.CURRENCY,
                "product_data": {
                    "name": p["name"],
                    "description": p["tagline"],
                },
                "unit_amount": price,
            },
            "quantity": ci["qty"],
        })
        items_json.append({"id": p["id"], "name": p["name"], "slug": p["slug"], "qty": ci["qty"], "price": price})

    # Free shipping included in pricing
    conn.close()

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=request.host_url + "order/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "cart",
            metadata={"items_json": json.dumps(items_json)},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@store_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    event_id = event.get("id", "")

    conn = get_db()
    # Replay protection — check if we've seen this event
    seen = conn.execute("SELECT event_id FROM stripe_events WHERE event_id = ?", (event_id,)).fetchone()
    if seen:
        conn.close()
        return jsonify({"status": "ok", "note": "duplicate_event"})

    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]

        # Idempotency — skip if already processed
        existing = conn.execute(
            "SELECT id FROM orders WHERE stripe_session_id = ?", (sess["id"],)
        ).fetchone()
        if existing:
            # Still record the event
            conn.execute("INSERT OR IGNORE INTO stripe_events (event_id, event_type) VALUES (?, ?)",
                        (event_id, event["type"]))
            conn.commit()
            conn.close()
            return jsonify({"status": "ok", "note": "duplicate"})

        items = json.loads(sess.get("metadata", {}).get("items_json", "[]"))

        # Begin immediate transaction to prevent race condition
        conn.execute("BEGIN IMMEDIATE")

        try:
            # Validate stock for all items before committing
            for item in items:
                row = conn.execute(
                    "SELECT stock, name FROM products WHERE slug = ?", (item.get("slug", ""),)
                ).fetchone()
                if row and row["stock"] < item.get("qty", 0):
                    conn.execute("ROLLBACK")
                    conn.close()
                    log.warning("Stock exhausted for %s during checkout", item.get("slug"))
                    return jsonify({"error": f"Insufficient stock for {row['name']}"}), 400

            # Calculate GST
            total_cents = sess.get("amount_total", 0)
            gst_cents = calculate_gst(total_cents)

            # Create order with GST
            conn.execute("""
                INSERT INTO orders (stripe_session_id, stripe_payment_intent, email, name, address,
                    items_json, total_cents, gst_cents, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'paid')
            """, (
                sess["id"],
                sess.get("payment_intent", ""),
                sess.get("customer_details", {}).get("email", ""),
                sess.get("customer_details", {}).get("name", ""),
                json.dumps(sess.get("shipping", {}).get("address", {})),
                sess.get("metadata", {}).get("items_json", "[]"),
                total_cents,
                gst_cents,
            ))

            # Decrement stock AND batch inventory for each item
            for item in items:
                slug = item.get("slug", "")
                qty = item.get("qty", 0)
                if slug and qty:
                    # Decrement products.stock
                    conn.execute(
                        "UPDATE products SET stock = stock - ? WHERE slug = ? AND stock >= ?",
                        (qty, slug, qty)
                    )
                    # Decrement batch inventory
                    conn.execute("""
                        UPDATE inventory_batches
                        SET units_sold = units_sold + ?
                        WHERE product_slug = ? AND status = 'active'
                    """, (qty, slug))

            # Record the processed event
            conn.execute("INSERT OR IGNORE INTO stripe_events (event_id, event_type) VALUES (?, ?)",
                        (event_id, event["type"]))

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            conn.close()
            raise

        # Get the order for email (after commit)
        order = conn.execute(
            "SELECT * FROM orders WHERE stripe_session_id = ?", (sess["id"],)
        ).fetchone()
        conn.close()

        # Send confirmation email (best effort)
        if order:
            send_order_confirmation(dict(order))

    return jsonify({"status": "ok"})


@store_bp.route("/order/success")
def order_success():
    session_id = request.args.get("session_id", "")
    return render_template("order_success.html", session_id=session_id)


# ── Legal pages ──

@store_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@store_bp.route("/terms")
def terms():
    return render_template("terms.html")


@store_bp.route("/track", methods=["GET", "POST"])
def track_order():
    orders = []
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
    else:
        query = request.args.get("query", "").strip()

    if query:
        conn = get_db()
        # Search by order ID, email, or stripe session ID
        try:
            order_id = int(query)
            orders = conn.execute(
                "SELECT * FROM orders WHERE id = ? ORDER BY created_at DESC", (order_id,)
            ).fetchall()
        except ValueError:
            orders = conn.execute(
                "SELECT * FROM orders WHERE email = ? ORDER BY created_at DESC", (query,)
            ).fetchall()
            if not orders:
                orders = conn.execute(
                    "SELECT * FROM orders WHERE stripe_session_id = ? ORDER BY created_at DESC", (query,)
                ).fetchall()
        conn.close()

        # Parse items for display
        parsed = []
        for o in orders:
            o = dict(o)
            o["items"] = json.loads(o.get("items_json", "[]"))
            parsed.append(o)
        orders = parsed

    return render_template("track.html", orders=orders, query=query)


# ── robots.txt + sitemap.xml ──

@store_bp.route("/robots.txt")
def robots_txt():
    base = request.host_url.rstrip("/")
    return f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cart/
Disallow: /checkout
Disallow: /webhook
Disallow: /chat/

Sitemap: {base}/sitemap.xml
""", 200, {"Content-Type": "text/plain"}


@store_bp.route("/sitemap.xml")
def sitemap_xml():
    conn = get_db()
    products = conn.execute("SELECT slug, created_at FROM products WHERE stock > 0").fetchall()
    conn.close()

    base = request.host_url.rstrip("/")
    urls = [
        f"<url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"<url><loc>{base}/privacy</loc><changefreq>monthly</changefreq></url>",
        f"<url><loc>{base}/terms</loc><changefreq>monthly</changefreq></url>",
        f"<url><loc>{base}/kb</loc><changefreq>weekly</changefreq></url>",
        f"<url><loc>{base}/track</loc><changefreq>yearly</changefreq></url>",
    ]
    for p in products:
        date = p["created_at"][:10] if p["created_at"] else ""
        urls.append(f'<url><loc>{base}/product/{p["slug"]}</loc>'
                    f'{"<lastmod>" + date + "</lastmod>" if date else ""}'
                    f"<changefreq>weekly</changefreq><priority>0.8</priority></url>")

    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    return xml, 200, {"Content-Type": "application/xml"}
