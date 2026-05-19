"""eBay listing MCP tools — CRUD for eBay listings and order sync triggers."""
import json
from datetime import datetime
from ..db.schema import get_conn


def list_ebay_listings(status: str = "") -> str:
    """List all tracked eBay listings, optionally filtered by status.

    Status options: draft, active, ended, error
    """
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT e.*, p.name as product_name, p.stock as web_stock "
                "FROM ebay_listings e JOIN products p ON e.product_slug = p.slug "
                "WHERE e.status = ? ORDER BY e.created_at DESC",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT e.*, p.name as product_name, p.stock as web_stock "
                "FROM ebay_listings e JOIN products p ON e.product_slug = p.slug "
                "ORDER BY e.created_at DESC"
            ).fetchall()

        if not rows:
            return f"No eBay listings found{f' with status {status}' if status else ''}."

        lines = [f"eBay Listings ({len(rows)}):\n"]
        for l in rows:
            lines.append(
                f"#{l['id']} [{l['status'].upper()}] {l['product_name']}\n"
                f"   SKU: {l['sku']} | eBay Price: ${l['ebay_price_cents']/100:.2f}\n"
                f"   Listed: {l['quantity_listed']} | Sold: {l['quantity_sold']} | Web Stock: {l['web_stock']}\n"
                f"   eBay URL: {l['ebay_url'] or 'N/A'}\n"
                f"   Last synced: {l['last_synced_at'][:16] if l['last_synced_at'] else 'Never'}\n"
                f"   Notes: {l['notes'] or 'N/A'}"
            )
        return "\n\n".join(lines)
    finally:
        conn.close()


def get_ebay_listing(sku: str) -> str:
    """Get details for a specific eBay listing by SKU."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT e.*, p.name as product_name, p.price_cents as web_price_cents, "
            "p.stock as web_stock, p.specs "
            "FROM ebay_listings e JOIN products p ON e.product_slug = p.slug "
            "WHERE e.sku = ?",
            (sku,)
        ).fetchone()

        if not row:
            return f"eBay listing '{sku}' not found."

        return (
            f"eBay Listing: {row['product_name']}\n"
            f"SKU: {row['sku']}\n"
            f"Status: {row['status'].upper()}\n"
            f"Product Slug: {row['product_slug']}\n"
            f"eBay Price: ${row['ebay_price_cents']/100:.2f}\n"
            f"Web Price: ${row['web_price_cents']/100:.2f}\n"
            f"Quantity Listed: {row['quantity_listed']}\n"
            f"Quantity Sold: {row['quantity_sold']}\n"
            f"Web Stock: {row['web_stock']}\n"
            f"eBay Offer ID: {row['ebay_offer_id'] or 'N/A'}\n"
            f"eBay Listing ID: {row['ebay_listing_id'] or 'N/A'}\n"
            f"eBay URL: {row['ebay_url'] or 'N/A'}\n"
            f"Listed at: {row['listed_at'] or 'N/A'}\n"
            f"Last synced: {row['last_synced_at'] or 'Never'}\n"
            f"Notes: {row['notes'] or 'N/A'}\n"
            f"Created: {row['created_at'][:16]}"
        )
    finally:
        conn.close()


def create_ebay_listing_draft(product_slug: str, ebay_price_cents: int = 0,
                               quantity: int = 1, notes: str = "") -> str:
    """Create an eBay listing draft in the database.

    The draft can later be published via the eBay Listing workflow or CSV upload.
    """
    conn = get_conn()
    try:
        # Verify product exists
        product = conn.execute(
            "SELECT name, price_cents FROM products WHERE slug = ?",
            (product_slug,)
        ).fetchone()
        if not product:
            return f"Error: Product '{product_slug}' not found."

        # Default price: web price + 5%
        if not ebay_price_cents:
            ebay_price_cents = int(product["price_cents"] * 1.05)

        sku = f"RZ-{product_slug}"

        # Check if listing already exists
        existing = conn.execute(
            "SELECT id FROM ebay_listings WHERE sku = ?", (sku,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE ebay_listings SET ebay_price_cents = ?, quantity_listed = ?, "
                "notes = ?, updated_at = ? WHERE sku = ?",
                (ebay_price_cents, quantity, notes,
                 datetime.utcnow().isoformat(), sku)
            )
            conn.commit()
            return (
                f"Updated eBay listing draft: {sku}\n"
                f"Product: {product['name']}\n"
                f"eBay Price: ${ebay_price_cents/100:.2f}\n"
                f"Quantity: {quantity}"
            )
        else:
            conn.execute(
                "INSERT INTO ebay_listings "
                "(product_slug, sku, ebay_price_cents, status, quantity_listed, notes) "
                "VALUES (?, ?, ?, 'draft', ?, ?)",
                (product_slug, sku, ebay_price_cents, quantity, notes)
            )
            conn.commit()
            return (
                f"Created eBay listing draft: {sku}\n"
                f"Product: {product['name']}\n"
                f"eBay Price: ${ebay_price_cents/100:.2f}\n"
                f"Quantity: {quantity}\n"
                f"Status: draft (ready for CSV upload or API publish)"
            )
    except Exception as e:
        return f"Error creating listing draft: {e}"
    finally:
        conn.close()


def sync_ebay_orders() -> str:
    """Trigger a manual eBay order sync. Polls eBay for new orders.

    Requires eBay API credentials to be configured.
    """
    try:
        # Run migration
        import subprocess
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "scripts", "ebay_order_sync.py"
        )
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=120
        )

        output = result.stdout or result.stderr
        if result.returncode != 0:
            return f"eBay sync error:\n{output}"

        return f"eBay order sync complete.\n{output}"
    except ImportError:
        return "eBay sync: credentials not configured. Set EBAY_CLIENT_ID etc in .env"
    except Exception as e:
        return f"Error triggering eBay sync: {e}"


# Need these imports for sync_ebay_orders
import os
import sys
