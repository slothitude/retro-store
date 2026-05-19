"""Knowledge base routes."""
from flask import Blueprint, render_template, request, redirect, url_for
from db import get_db

kb_bp = Blueprint("kb", __name__, url_prefix="/kb")


@kb_bp.route("/")
def index():
    conn = get_db()
    categories = conn.execute("""
        SELECT category, COUNT(*) as count
        FROM kb_articles WHERE published = 1
        GROUP BY category ORDER BY category
    """).fetchall()
    articles = conn.execute("""
        SELECT * FROM kb_articles WHERE published = 1
        ORDER BY category, sort_order, title
    """).fetchall()
    conn.close()
    return render_template("kb/index.html", categories=categories, articles=articles)


@kb_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("kb.index"))

    conn = get_db()
    results = conn.execute("""
        SELECT kb_articles.* FROM kb_articles
        JOIN kb_fts ON kb_fts.article_id = kb_articles.id
        JOIN kb_search ON kb_search.rowid = kb_fts.id
        WHERE kb_search MATCH ?
        AND kb_articles.published = 1
        ORDER BY rank
    """, (q,)).fetchall()
    conn.close()
    return render_template("kb/search.html", results=results, query=q)


@kb_bp.route("/<slug>")
def article(slug):
    conn = get_db()
    art = conn.execute("SELECT * FROM kb_articles WHERE slug = ? AND published = 1", (slug,)).fetchone()
    if not art:
        conn.close()
        return render_template("404.html"), 404
    # Get related articles in same category
    related = conn.execute("""
        SELECT * FROM kb_articles WHERE category = ? AND slug != ? AND published = 1
        LIMIT 5
    """, (art["category"], slug)).fetchall()
    conn.close()
    return render_template("kb/article.html", article=art, related=related)
