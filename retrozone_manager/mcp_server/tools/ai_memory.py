"""AI memory tools — log decisions, take notes, search history."""
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db import get_db


def log_decision(decision_type: str, product_slug: str, decision: str,
                 reasoning: str = "", data_used: str = "", confidence: str = "medium") -> str:
    """Log an AI decision with reasoning for future reference.

    Args:
        decision_type: One of 'price_change', 'restock', 'listing', 'analysis', 'strategy'
        product_slug: Related product slug (empty string if general)
        decision: The decision made
        reasoning: Why this decision was made
        data_used: JSON string of data that informed the decision
        confidence: 'low', 'medium', or 'high'
    """
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO ai_decisions (decision_type, product_slug, decision, reasoning, data_used, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (decision_type, product_slug, decision, reasoning, data_used, confidence)
    )
    conn.commit()
    decision_id = cursor.lastrowid
    conn.close()
    return f"Decision #{decision_id} logged: {decision_type} for {product_slug or 'general'}"


def add_note(category: str, subject: str, body: str,
             related_slug: str = "", importance: str = "normal") -> str:
    """Add a persistent AI note.

    Args:
        category: One of 'supplier', 'product', 'market', 'strategy', 'lesson'
        subject: Short subject line
        body: Full note content
        related_slug: Related product slug (optional)
        importance: 'low', 'normal', or 'high'
    """
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO ai_notes (category, subject, body, related_slug, importance) "
        "VALUES (?, ?, ?, ?, ?)",
        (category, subject, body, related_slug, importance)
    )
    note_id = cursor.lastrowid

    # Insert FTS row
    conn.execute(
        "INSERT INTO ai_notes_fts (note_id, subject, body) VALUES (?, ?, ?)",
        (note_id, subject, body)
    )
    conn.commit()
    conn.close()
    return f"Note #{note_id} added: [{category}] {subject}"


def search_decisions(product_slug: str = "", decision_type: str = "",
                     limit: int = 20) -> str:
    """Search AI decision history.

    Args:
        product_slug: Filter by product slug (optional)
        decision_type: Filter by type (optional)
        limit: Max results to return
    """
    conn = get_db()
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

    if not rows:
        return "No decisions found."

    results = []
    for r in rows:
        results.append(
            f"#{r['id']} [{r['decision_type']}] {r['product_slug'] or 'general'}\n"
            f"  Decision: {r['decision']}\n"
            f"  Reasoning: {r['reasoning']}\n"
            f"  Confidence: {r['confidence']}\n"
            f"  Outcome: {r['outcome'] or '(pending)'}\n"
            f"  Time: {r['created_at']}"
        )
    return f"Found {len(rows)} decision(s):\n\n" + "\n\n".join(results)


def search_notes(query: str, category: str = "", limit: int = 20) -> str:
    """Search AI notes using FTS5 full-text search.

    Args:
        query: Search terms
        category: Filter by category (optional)
        limit: Max results to return
    """
    conn = get_db()

    # FTS5 search
    fts_query = "SELECT rowid FROM ai_notes_search WHERE ai_notes_search MATCH ?"
    fts_params = [query]

    fts_results = conn.execute(fts_query, fts_params).fetchall()
    rowids = [r[0] for r in fts_results]

    if not rowids:
        # Fallback to LIKE search
        like_query = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM ai_notes WHERE (subject LIKE ? OR body LIKE ?) "
            + ("AND category = ?" if category else ""),
            [like_query, like_query] + ([category] if category else [])
        ).fetchall()
    else:
        # Get full notes by FTS matches
        placeholders = ",".join("?" * len(rowids))
        sql = f"SELECT * FROM ai_notes WHERE id IN ({placeholders})"
        params = list(rowids)
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()

    conn.close()

    if not rows:
        return f"No notes found for '{query}'."

    results = []
    for r in rows:
        results.append(
            f"#{r['id']} [{r['category']}] {r['subject']}\n"
            f"  {r['body']}\n"
            f"  Product: {r['related_slug'] or 'general'} | Importance: {r['importance']}\n"
            f"  Time: {r['created_at']}"
        )
    return f"Found {len(rows)} note(s):\n\n" + "\n\n".join(results)
