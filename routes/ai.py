"""AI admin panel — decisions log, notes CRUD."""
import json
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from routes.admin import admin_required

log = logging.getLogger("retromonkey.ai")

ai_bp = Blueprint("ai", __name__, url_prefix="/admin/ai")


# ── Decision Log ──

@ai_bp.route("/decisions")
@admin_required
def decisions():
    conn = get_db()
    decision_type = request.args.get("type", "")
    product_slug = request.args.get("slug", "")
    limit = request.args.get("limit", 50, type=int)

    query = "SELECT * FROM ai_decisions WHERE 1=1"
    params = []
    if decision_type:
        query += " AND decision_type = ?"
        params.append(decision_type)
    if product_slug:
        query += " AND product_slug = ?"
        params.append(product_slug)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    # Get unique types and slugs for filters
    types = conn.execute("SELECT DISTINCT decision_type FROM ai_decisions ORDER BY decision_type").fetchall()
    slugs = conn.execute("SELECT DISTINCT product_slug FROM ai_decisions WHERE product_slug != '' ORDER BY product_slug").fetchall()
    conn.close()

    return render_template("admin/ai_decisions.html",
                         decisions=[dict(r) for r in rows],
                         types=[t[0] for t in types],
                         slugs=[s[0] for s in slugs],
                         filter_type=decision_type,
                         filter_slug=product_slug)


# ── Notes ──

@ai_bp.route("/notes")
@admin_required
def notes():
    conn = get_db()
    category = request.args.get("category", "")
    q = request.args.get("q", "")
    limit = request.args.get("limit", 50, type=int)

    if q:
        # FTS5 search
        try:
            fts_results = conn.execute(
                "SELECT rowid FROM ai_notes_search WHERE ai_notes_search MATCH ?", (q,)
            ).fetchall()
            rowids = [r[0] for r in fts_results]
            if rowids:
                placeholders = ",".join("?" * len(rowids))
                sql = f"SELECT * FROM ai_notes WHERE id IN ({placeholders})"
                params = list(rowids)
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                sql += " ORDER BY updated_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
            else:
                rows = []
        except Exception:
            # FTS5 can error on weird queries — fallback to LIKE
            like = f"%{q}%"
            rows = conn.execute(
                "SELECT * FROM ai_notes WHERE (subject LIKE ? OR body LIKE ?) "
                + ("AND category = ?" if category else "")
                + " ORDER BY updated_at DESC LIMIT ?",
                [like, like] + ([category] if category else []) + [limit]
            ).fetchall()
    elif category:
        rows = conn.execute(
            "SELECT * FROM ai_notes WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ai_notes ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()

    categories = conn.execute("SELECT DISTINCT category FROM ai_notes ORDER BY category").fetchall()
    conn.close()

    return render_template("admin/ai_notes.html",
                         notes=[dict(r) for r in rows],
                         categories=[c[0] for c in categories],
                         filter_category=category,
                         search_query=q)


@ai_bp.route("/notes/new", methods=["GET", "POST"])
@admin_required
def note_new():
    if request.method == "POST":
        category = request.form.get("category", "general")
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        related_slug = request.form.get("related_slug", "").strip()
        importance = request.form.get("importance", "normal")

        if not subject or not body:
            flash("Subject and body are required.", "error")
            return render_template("admin/ai_note_form.html", note=None)

        conn = get_db()
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

        flash(f"Note '{subject}' created.", "success")
        return redirect(url_for("ai.notes"))

    return render_template("admin/ai_note_form.html", note=None)


@ai_bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
@admin_required
def note_edit(note_id):
    conn = get_db()
    note = conn.execute("SELECT * FROM ai_notes WHERE id = ?", (note_id,)).fetchone()
    if not note:
        conn.close()
        flash("Note not found.", "error")
        return redirect(url_for("ai.notes"))

    if request.method == "POST":
        category = request.form.get("category", "general")
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        related_slug = request.form.get("related_slug", "").strip()
        importance = request.form.get("importance", "normal")

        if not subject or not body:
            flash("Subject and body are required.", "error")
            return render_template("admin/ai_note_form.html", note=dict(note))

        # Update FTS
        conn.execute("DELETE FROM ai_notes_fts WHERE note_id = ?", (note_id,))
        conn.execute(
            "INSERT INTO ai_notes_fts (note_id, subject, body) VALUES (?, ?, ?)",
            (note_id, subject, body)
        )

        conn.execute("""
            UPDATE ai_notes SET category=?, subject=?, body=?, related_slug=?,
                importance=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (category, subject, body, related_slug, importance, note_id))
        conn.commit()
        conn.close()

        flash(f"Note '{subject}' updated.", "success")
        return redirect(url_for("ai.notes"))

    conn.close()
    return render_template("admin/ai_note_form.html", note=dict(note))


@ai_bp.route("/notes/<int:note_id>/delete", methods=["POST"])
@admin_required
def note_delete(note_id):
    conn = get_db()
    conn.execute("DELETE FROM ai_notes_fts WHERE note_id = ?", (note_id,))
    conn.execute("DELETE FROM ai_notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    flash("Note deleted.", "success")
    return redirect(url_for("ai.notes"))
