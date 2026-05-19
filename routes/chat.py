"""Live chat routes (AJAX-based polling)."""
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from db import get_db
import config

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


def get_session_id():
    if "chat_session" not in session:
        session["chat_session"] = str(uuid.uuid4())
    return session["chat_session"]


@chat_bp.route("/widget")
def widget():
    return render_template("chat/widget.html")


@chat_bp.route("/messages")
def messages():
    session_id = get_session_id()
    after_id = request.args.get("after", 0, type=int)
    conn = get_db()
    msgs = conn.execute("""
        SELECT * FROM chat_messages
        WHERE session_id = ? AND id > ?
        ORDER BY id ASC
    """, (session_id, after_id)).fetchall()
    conn.close()
    return jsonify([dict(m) for m in msgs])


@chat_bp.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    session_id = get_session_id()
    visitor_name = data.get("name", "Visitor")

    conn = get_db()
    conn.execute("""
        INSERT INTO chat_messages (session_id, visitor_name, message, is_admin)
        VALUES (?, ?, ?, 0)
    """, (session_id, visitor_name, message))
    conn.commit()
    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    return jsonify({"id": msg_id, "ok": True})


@chat_bp.route("/admin/messages")
def admin_messages():
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401

    conn = get_db()
    # Get all active sessions with latest message
    sessions = conn.execute("""
        SELECT session_id, visitor_name, MAX(created_at) as last_msg,
               SUM(CASE WHEN is_admin = 0 THEN 1 ELSE 0 END) as unread
        FROM chat_messages
        GROUP BY session_id
        ORDER BY last_msg DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sessions])


@chat_bp.route("/admin/reply", methods=["POST"])
def admin_reply():
    if not session.get("admin"):
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()
    session_id = data.get("session_id", "")
    message = data.get("message", "").strip()
    if not message or not session_id:
        return jsonify({"error": "Missing data"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO chat_messages (session_id, visitor_name, message, is_admin)
        VALUES (?, 'Support', ?, 1)
    """, (session_id, message))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
