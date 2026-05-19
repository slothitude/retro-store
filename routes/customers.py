"""Customer account routes."""
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
from app import limiter

customers_bp = Blueprint("customers", __name__)


def customer_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("customer_id"):
            flash("Please log in to access your account.", "error")
            return redirect(url_for("customers.login"))
        return f(*args, **kwargs)
    return decorated


@customers_bp.route("/account/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()

        if not email or not password or len(password) < 8:
            flash("Email and password (8+ characters) are required.", "error")
            return render_template("customers/register.html")

        conn = get_db()
        existing = conn.execute("SELECT id FROM customers WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with that email already exists.", "error")
            return render_template("customers/register.html")

        pw_hash = generate_password_hash(password)
        conn.execute("INSERT INTO customers (email, password_hash, name) VALUES (?, ?, ?)",
                    (email, pw_hash, name))
        conn.commit()
        customer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        session["customer_id"] = customer_id
        session["customer_email"] = email
        session["customer_name"] = name
        flash("Account created! Welcome to RetroZone.", "success")
        return redirect(url_for("customers.account"))

    return render_template("customers/register.html")


@customers_bp.route("/account/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        customer = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
        conn.close()

        if customer and check_password_hash(customer["password_hash"], password):
            session["customer_id"] = customer["id"]
            session["customer_email"] = customer["email"]
            session["customer_name"] = customer["name"]
            flash("Logged in.", "success")
            return redirect(url_for("customers.account"))

        flash("Invalid email or password.", "error")
    return render_template("customers/login.html")


@customers_bp.route("/account/logout")
def logout():
    session.pop("customer_id", None)
    session.pop("customer_email", None)
    session.pop("customer_name", None)
    flash("Logged out.", "success")
    return redirect(url_for("store.index"))


@customers_bp.route("/account")
@customer_login_required
def account():
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id = ?",
                           (session["customer_id"],)).fetchone()
    orders = conn.execute(
        "SELECT * FROM orders WHERE email = ? ORDER BY created_at DESC",
        (session["customer_email"],)
    ).fetchall()

    # Parse items for display
    parsed_orders = []
    for o in orders:
        o = dict(o)
        o["items"] = json.loads(o.get("items_json", "[]"))
        parsed_orders.append(o)

    conn.close()
    return render_template("customers/account.html", customer=dict(customer), orders=parsed_orders)


@customers_bp.route("/account/address", methods=["POST"])
@customer_login_required
def update_address():
    address = {
        "line1": request.form.get("line1", "").strip(),
        "line2": request.form.get("line2", "").strip(),
        "city": request.form.get("city", "").strip(),
        "state": request.form.get("state", "").strip(),
        "postal_code": request.form.get("postal_code", "").strip(),
        "country": "AU",
    }
    conn = get_db()
    conn.execute("UPDATE customers SET address = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(address), session["customer_id"]))
    conn.commit()
    conn.close()
    flash("Address updated.", "success")
    return redirect(url_for("customers.account"))
