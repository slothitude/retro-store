"""Store routes — products, cart, checkout."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import json
import stripe
from db import get_db, get_active_batch, get_batch_price, get_batch_phase, get_batch_remaining
import config

store_bp = Blueprint("store", __name__)


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


@store_bp.context_processor
def inject_cart():
    return {"cart_items": cart_item_count()}


# ── Public pages ──

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

    # Enrich products with batch pricing
    for plist in (featured, all_products):
        for i, p in enumerate(plist):
            p = dict(p)
            batch = get_active_batch(p['slug'])
            if batch and get_batch_remaining(batch) > 0:
                p['batch_price_cents'] = get_batch_price(batch)
                p['batch_phase'] = get_batch_phase(batch)
                p['batch_remaining'] = get_batch_remaining(batch)
                p['batch_cost_cents'] = batch['cost_per_unit_cents']
                p['batch_arrives_at'] = batch['arrives_at']
            plist[i] = p

    return render_template("index.html", featured=featured, products=all_products)


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
    return render_template("cart.html", items=items, total=total)


@store_bp.route("/cart/add", methods=["POST"])
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

    # Free shipping on all orders (included in batch pricing)
    shipping = 0

    return render_template("checkout.html", items=items, total=total, shipping=shipping,
                         stripe_key=config.STRIPE_PUBLIC_KEY)


@store_bp.route("/create-checkout-session", methods=["POST"])
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

    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        conn = get_db()
        conn.execute("""
            INSERT INTO orders (stripe_session_id, stripe_payment_intent, email, name, address,
                items_json, total_cents, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid')
        """, (
            sess["id"],
            sess.get("payment_intent", ""),
            sess.get("customer_details", {}).get("email", ""),
            sess.get("customer_details", {}).get("name", ""),
            json.dumps(sess.get("shipping", {}).get("address", {})),
            sess.get("metadata", {}).get("items_json", "[]"),
            sess.get("amount_total", 0),
        ))
        # Decrement batch inventory for each item
        items = json.loads(sess.get("metadata", {}).get("items_json", "[]"))
        for item in items:
            slug = item.get("slug", "")
            qty = item.get("qty", 0)
            if slug and qty:
                conn.execute("""
                    UPDATE inventory_batches
                    SET units_sold = units_sold + ?
                    WHERE product_slug = ? AND status = 'active'
                """, (qty, slug))
        conn.commit()
        conn.close()

    return jsonify({"status": "ok"})


@store_bp.route("/order/success")
def order_success():
    session_id = request.args.get("session_id", "")
    return render_template("order_success.html", session_id=session_id)
