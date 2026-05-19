"""Ticket system routes."""
import json
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
import config
from app import limiter

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def gen_key():
    """Generate a ticket key like TK-AB12CD."""
    return f"TK-{uuid.uuid4().hex[:5].upper()}"


@tickets_bp.route("/new", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def new():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        name = request.form.get("name", "").strip()
        subject = request.form.get("subject", "").strip()
        order_ref = request.form.get("order_ref", "").strip()
        category = request.form.get("category", "general")
        message = request.form.get("message", "").strip()

        if not email or not subject or not message:
            flash("Please fill in all required fields.", "error")
            return render_template("tickets/new.html")

        key = gen_key()
        messages = [{"from": "customer", "text": message, "time": datetime.utcnow().isoformat()}]

        conn = get_db()
        conn.execute("""
            INSERT INTO tickets (ticket_key, email, name, subject, order_ref, category, messages_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (key, email, name, subject, order_ref, category, json.dumps(messages)))
        conn.commit()
        conn.close()

        flash(f"Ticket created! Your ticket key is {key}. Save this to check status.", "success")
        return render_template("tickets/submitted.html", key=key)

    return render_template("tickets/new.html")


@tickets_bp.route("/lookup", methods=["GET", "POST"])
def lookup():
    ticket = None
    key = request.args.get("key", "").strip()

    if request.method == "POST":
        key = request.form.get("key", "").strip()

    if key:
        conn = get_db()
        ticket = conn.execute("SELECT * FROM tickets WHERE ticket_key = ?", (key,)).fetchone()
        if ticket:
            ticket = dict(ticket)
            ticket["messages"] = json.loads(ticket["messages_json"])
        conn.close()

    return render_template("tickets/lookup.html", ticket=ticket, key=key)
