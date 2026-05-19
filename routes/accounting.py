"""Accounting routes — expenses, BAS, P&L, CSV export."""
import csv
import io
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from db import get_db
import config

log = logging.getLogger("retromonkey.accounting")

accounting_bp = Blueprint("accounting", __name__, url_prefix="/admin/accounting")


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Admin login required.", "error")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ──

@accounting_bp.route("/")
@admin_required
def dashboard():
    conn = get_db()

    # Date range filter
    days = request.args.get("days", 30, type=int)

    # Revenue stats (from orders)
    revenue = conn.execute("""
        SELECT
            COUNT(*) as order_count,
            COALESCE(SUM(total_cents), 0) as total_revenue,
            COALESCE(SUM(gst_cents), 0) as gst_collected,
            COALESCE(SUM(shipping_cents), 0) as shipping_revenue
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= datetime('now', ? || ' days')
    """, (-days,)).fetchone()

    # COGS from batches
    cogs = conn.execute("""
        SELECT COALESCE(SUM(units_sold * cost_per_unit_cents), 0)
        FROM inventory_batches
    """).fetchone()[0]

    # Expenses
    expenses_total = conn.execute("""
        SELECT
            COALESCE(SUM(amount_cents), 0) as total,
            COALESCE(SUM(gst_cents), 0) as gst
        FROM expenses
        WHERE date >= date('now', ? || ' days')
    """, (-days,)).fetchone()

    # Calculate net
    total_expenses = expenses_total["total"]
    expense_gst = expenses_total["gst"]
    total_revenue = revenue["total_revenue"]
    gst_collected = revenue["gst_collected"]
    gross_profit = total_revenue - cogs
    net_profit = gross_profit - total_expenses
    net_gst = gst_collected - expense_gst

    margin = round(gross_profit / total_revenue * 100, 1) if total_revenue else 0
    net_margin = round(net_profit / total_revenue * 100, 1) if total_revenue else 0

    # Recent expenses
    recent_expenses = conn.execute("""
        SELECT e.*, c.name as category_name
        FROM expenses e
        JOIN expense_categories c ON c.id = e.category_id
        ORDER BY e.date DESC, e.id DESC
        LIMIT 10
    """).fetchall()

    # Expense breakdown by category
    category_breakdown = conn.execute("""
        SELECT c.name, COALESCE(SUM(e.amount_cents), 0) as total,
               COALESCE(SUM(e.gst_cents), 0) as gst
        FROM expense_categories c
        LEFT JOIN expenses e ON e.category_id = c.id
        WHERE e.date >= date('now', ? || ' days') OR e.date IS NULL
        GROUP BY c.id, c.name
        HAVING total > 0
        ORDER BY total DESC
    """, (-days,)).fetchall()

    # Monthly revenue trend (last 6 months)
    monthly = conn.execute("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as orders,
            COALESCE(SUM(total_cents), 0) as revenue,
            COALESCE(SUM(gst_cents), 0) as gst
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= datetime('now', '-180 days')
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month DESC
    """).fetchall()

    conn.close()

    return render_template("admin/accounting.html",
        days=days,
        revenue=dict(revenue),
        cogs=cogs,
        total_expenses=total_expenses,
        gross_profit=gross_profit,
        net_profit=net_profit,
        margin=margin,
        net_margin=net_margin,
        gst_collected=gst_collected,
        expense_gst=expense_gst,
        net_gst=net_gst,
        recent_expenses=recent_expenses,
        category_breakdown=category_breakdown,
        monthly=monthly,
    )


# ── Expenses CRUD ──

@accounting_bp.route("/expenses")
@admin_required
def expenses():
    conn = get_db()
    category_filter = request.args.get("category", "", type=str)
    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    query = """
        SELECT e.*, c.name as category_name
        FROM expenses e
        JOIN expense_categories c ON c.id = e.category_id
        WHERE 1=1
    """
    params = []

    if category_filter:
        query += " AND c.name = ?"
        params.append(category_filter)
    if date_from:
        query += " AND e.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND e.date <= ?"
        params.append(date_to)

    query += " ORDER BY e.date DESC, e.id DESC"

    rows = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()

    # Summary stats
    total = conn.execute("""
        SELECT COALESCE(SUM(amount_cents), 0), COALESCE(SUM(gst_cents), 0)
        FROM expenses e
        JOIN expense_categories c ON c.id = e.category_id
        WHERE 1=1
    """ + (" AND c.name = ?" if category_filter else "") + (" AND e.date >= ?" if date_from else "") + (" AND e.date <= ?" if date_to else ""),
        params).fetchone()

    conn.close()
    return render_template("admin/expenses.html",
        expenses=rows,
        categories=categories,
        category_filter=category_filter,
        date_from=date_from,
        date_to=date_to,
        total_amount=total[0],
        total_gst=total[1],
    )


@accounting_bp.route("/expenses/new", methods=["GET", "POST"])
@admin_required
def expense_new():
    conn = get_db()
    categories = conn.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()

    if request.method == "POST":
        date = request.form.get("date", "").strip()
        category_id = request.form.get("category_id", type=int)
        description = request.form.get("description", "").strip()
        amount = request.form.get("amount", "").strip()
        supplier = request.form.get("supplier", "").strip()
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        includes_gst = request.form.get("includes_gst") == "1"

        if not all([date, category_id, description, amount]):
            conn.close()
            flash("Date, category, description, and amount are required.", "error")
            return render_template("admin/expense_form.html", categories=categories, expense=None)

        # Parse amount (accept $XX.XX format)
        amount_clean = amount.replace("$", "").replace(",", "").strip()
        try:
            amount_cents = int(float(amount_clean) * 100)
        except ValueError:
            conn.close()
            flash("Invalid amount.", "error")
            return render_template("admin/expense_form.html", categories=categories, expense=None)

        # Calculate GST component (10%)
        gst_cents = 0
        if includes_gst:
            # Amount includes GST: GST = amount - (amount / 1.10)
            gst_cents = amount_cents - int(amount_cents / 1.10)

        conn.execute("""
            INSERT INTO expenses (date, category_id, description, amount_cents, gst_cents,
                supplier, reference, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, category_id, description, amount_cents, gst_cents,
              supplier, reference, notes))
        conn.commit()
        conn.close()

        flash(f"Expense '${amount}' recorded.", "success")
        log.info("Expense recorded: %s — $%s", description, amount)
        return redirect(url_for("accounting.expenses"))

    conn.close()
    return render_template("admin/expense_form.html", categories=categories, expense=None)


@accounting_bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@admin_required
def expense_edit(expense_id):
    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        flash("Expense not found.", "error")
        return redirect(url_for("accounting.expenses"))

    categories = conn.execute("SELECT * FROM expense_categories ORDER BY name").fetchall()

    if request.method == "POST":
        date = request.form.get("date", "").strip()
        category_id = request.form.get("category_id", type=int)
        description = request.form.get("description", "").strip()
        amount = request.form.get("amount", "").strip()
        supplier = request.form.get("supplier", "").strip()
        reference = request.form.get("reference", "").strip()
        notes = request.form.get("notes", "").strip()
        includes_gst = request.form.get("includes_gst") == "1"

        amount_clean = amount.replace("$", "").replace(",", "").strip()
        try:
            amount_cents = int(float(amount_clean) * 100)
        except ValueError:
            flash("Invalid amount.", "error")
            return render_template("admin/expense_form.html", categories=categories,
                                 expense=dict(expense))

        gst_cents = 0
        if includes_gst:
            gst_cents = amount_cents - int(amount_cents / 1.10)

        conn.execute("""
            UPDATE expenses SET date=?, category_id=?, description=?, amount_cents=?,
                gst_cents=?, supplier=?, reference=?, notes=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (date, category_id, description, amount_cents, gst_cents,
              supplier, reference, notes, expense_id))
        conn.commit()
        conn.close()

        flash("Expense updated.", "success")
        return redirect(url_for("accounting.expenses"))

    expense = dict(expense)
    conn.close()
    return render_template("admin/expense_form.html", categories=categories, expense=expense)


@accounting_bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@admin_required
def expense_delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    flash("Expense deleted.", "success")
    return redirect(url_for("accounting.expenses"))


# ── BAS (Business Activity Statement) ──

@accounting_bp.route("/bas")
@admin_required
def bas():
    conn = get_db()

    # Get available quarters
    quarters = []
    for year_offset in range(2):
        year = datetime.now().year - year_offset
        for q_start, q_end, label in [
            (f"{year}-01-01", f"{year}-03-31", f"Q1 {year} (Jan-Mar)"),
            (f"{year}-04-01", f"{year}-06-30", f"Q2 {year} (Apr-Jun)"),
            (f"{year}-07-01", f"{year}-09-30", f"Q3 {year} (Jul-Sep)"),
            (f"{year}-10-01", f"{year}-12-31", f"Q4 {year} (Oct-Dec)"),
        ]:
            quarters.append({"start": q_start, "end": q_end, "label": label})
    quarters = quarters[:8]  # Last 8 quarters

    # Selected quarter
    q_from = request.args.get("from", quarters[0]["start"])
    q_to = request.args.get("to", quarters[0]["end"])

    # GST on sales (collected)
    sales = conn.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(total_cents), 0) as total,
            COALESCE(SUM(gst_cents), 0) as gst
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= ? AND created_at <= ? || ' 23:59:59'
    """, (q_from, q_to)).fetchone()

    # GST on purchases (paid)
    purchases = conn.execute("""
        SELECT
            COUNT(*) as count,
            COALESCE(SUM(amount_cents), 0) as total,
            COALESCE(SUM(gst_cents), 0) as gst
        FROM expenses
        WHERE date >= ? AND date <= ?
    """, (q_from, q_to)).fetchone()

    # Breakdown by expense category
    category_gst = conn.execute("""
        SELECT c.name, COALESCE(SUM(e.amount_cents), 0) as total,
               COALESCE(SUM(e.gst_cents), 0) as gst
        FROM expense_categories c
        LEFT JOIN expenses e ON e.category_id = c.id
            AND e.date >= ? AND e.date <= ?
        GROUP BY c.id, c.name
        HAVING total > 0
        ORDER BY total DESC
    """, (q_from, q_to)).fetchall()

    conn.close()

    net_gst = sales["gst"] - purchases["gst"]
    selected_label = next(
        (q["label"] for q in quarters if q["start"] == q_from and q["end"] == q_to),
        f"{q_from} to {q_to}"
    )

    return render_template("admin/bas.html",
        quarters=quarters,
        q_from=q_from,
        q_to=q_to,
        selected_label=selected_label,
        sales=dict(sales),
        purchases=dict(purchases),
        category_gst=category_gst,
        net_gst=net_gst,
    )


# ── Full P&L Report ──

@accounting_bp.route("/pnl")
@admin_required
def full_pnl():
    conn = get_db()
    days = request.args.get("days", 30, type=int)

    # Revenue
    revenue = conn.execute("""
        SELECT
            COUNT(*) as order_count,
            COALESCE(SUM(total_cents), 0) as total_revenue,
            COALESCE(SUM(gst_cents), 0) as gst,
            COALESCE(SUM(shipping_cents), 0) as shipping
        FROM orders
        WHERE status IN ('paid', 'shipped', 'delivered')
        AND created_at >= datetime('now', ? || ' days')
    """, (-days,)).fetchone()

    # COGS
    cogs = conn.execute("""
        SELECT COALESCE(SUM(units_sold * cost_per_unit_cents), 0)
        FROM inventory_batches
    """).fetchone()[0]

    # Expenses by category
    expense_rows = conn.execute("""
        SELECT c.name, COALESCE(SUM(e.amount_cents), 0) as total,
               COALESCE(SUM(e.gst_cents), 0) as gst
        FROM expense_categories c
        LEFT JOIN expenses e ON e.category_id = c.id
            AND e.date >= date('now', ? || ' days')
        GROUP BY c.id, c.name
        ORDER BY total DESC
    """, (-days,)).fetchall()

    total_expenses = sum(r["total"] for r in expense_rows)
    total_expense_gst = sum(r["gst"] for r in expense_rows)
    gross_profit = revenue["total_revenue"] - cogs
    net_profit = gross_profit - total_expenses
    net_gst = revenue["gst"] - total_expense_gst

    conn.close()

    return render_template("admin/accounting_pnl.html",
        days=days,
        revenue=dict(revenue),
        cogs=cogs,
        gross_profit=gross_profit,
        expenses=expense_rows,
        total_expenses=total_expenses,
        net_profit=net_profit,
        net_gst=net_gst,
    )


# ── CSV Export ──

@accounting_bp.route("/export")
@admin_required
def export_csv():
    export_type = request.args.get("type", "all")
    days = request.args.get("days", 365, type=int)

    output = io.StringIO()
    writer = csv.writer(output)

    if export_type in ("all", "orders"):
        writer.writerow(["=== ORDERS ==="])
        writer.writerow(["Order ID", "Date", "Email", "Status", "Total (AUD)", "GST (AUD)",
                         "Shipping (AUD)", "Items"])

        conn = get_db()
        orders = conn.execute("""
            SELECT * FROM orders
            WHERE created_at >= datetime('now', ? || ' days')
            ORDER BY created_at DESC
        """, (-days,)).fetchall()
        conn.close()

        for o in orders:
            items = json.loads(o["items_json"])
            items_str = "; ".join(f"{i.get('name','')} x{i.get('qty',0)}" for i in items)
            writer.writerow([
                o["id"], o["created_at"][:10], o["email"], o["status"],
                f"{o['total_cents']/100:.2f}", f"{o.get('gst_cents',0)/100:.2f}",
                f"{o.get('shipping_cents',0)/100:.2f}", items_str,
            ])
        writer.writerow([])

    if export_type in ("all", "expenses"):
        writer.writerow(["=== EXPENSES ==="])
        writer.writerow(["Date", "Category", "Description", "Amount (AUD)", "GST (AUD)",
                         "Supplier", "Reference", "Notes"])

        conn = get_db()
        expenses = conn.execute("""
            SELECT e.*, c.name as category_name
            FROM expenses e
            JOIN expense_categories c ON c.id = e.category_id
            WHERE e.date >= date('now', ? || ' days')
            ORDER BY e.date DESC
        """, (-days,)).fetchall()
        conn.close()

        for e in expenses:
            writer.writerow([
                e["date"], e["category_name"], e["description"],
                f"{e['amount_cents']/100:.2f}", f"{e['gst_cents']/100:.2f}",
                e["supplier"], e["reference"], e["notes"],
            ])
        writer.writerow([])

    if export_type == "all":
        writer.writerow(["=== SUMMARY ==="])
        writer.writerow(["Report generated:", datetime.now().strftime("%Y-%m-%d %H:%M")])
        writer.writerow(["Period:", f"Last {days} days"])
        writer.writerow(["Business:", config.BUSINESS_NAME])
        if config.ABN:
            writer.writerow(["ABN:", config.ABN])

    output.seek(0)
    filename = f"retromonkey_{export_type}_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Expense Categories Management ──

@accounting_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if name:
            try:
                conn.execute("INSERT INTO expense_categories (name, description) VALUES (?, ?)",
                           (name, description))
                conn.commit()
                flash(f"Category '{name}' created.", "success")
            except Exception:
                flash("Category already exists.", "error")
        else:
            flash("Category name is required.", "error")

    cats = conn.execute("""
        SELECT c.*, COUNT(e.id) as expense_count, COALESCE(SUM(e.amount_cents), 0) as total
        FROM expense_categories c
        LEFT JOIN expenses e ON e.category_id = c.id
        GROUP BY c.id, c.name, c.description, c.is_default
        ORDER BY c.name
    """).fetchall()
    conn.close()

    return render_template("admin/expense_categories.html", categories=cats)
