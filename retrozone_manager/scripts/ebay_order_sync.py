"""eBay order sync — polls eBay for new orders and syncs to RetroZone.

Usage:
    python retrozone_manager/scripts/ebay_order_sync.py
    python retrozone_manager/scripts/ebay_order_sync.py --dry-run

Run via Task Scheduler every 30 min:
    schtasks /create /tn "RetroZone-eBay-Sync" /tr "python C:\\Users\\aaron\\Desktop\\dev\\retro-store\\retrozone_manager\\scripts\\ebay_order_sync.py" /sc minute /mo 30
"""
import json
import os
import sys
import argparse
import logging
from datetime import datetime

# Add parent dirs to path for imports
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from retrozone_manager.mcp_server.db.schema import get_conn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [eBay Sync] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(ROOT, "retrozone_manager", "scripts", "ebay_sync.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def add_source_column():
    """Add 'source' column to orders table if it doesn't exist."""
    conn = get_conn()
    try:
        # Check if column exists
        cols = conn.execute("PRAGMA table_info(orders)").fetchall()
        col_names = [c[1] for c in cols]
        if "source" not in col_names:
            conn.execute("ALTER TABLE orders ADD COLUMN source TEXT DEFAULT 'web'")
            conn.commit()
            log.info("Added 'source' column to orders table")
    except Exception as e:
        log.error(f"Migration error: {e}")
    finally:
        conn.close()


def sync_orders(dry_run=False):
    """Poll eBay for new orders and insert into orders table."""
    try:
        from retrozone_manager.ebay_client import EbayClient
    except ImportError:
        log.error("Cannot import EbayClient. Ensure ebay_client.py exists.")
        return

    # Check credentials
    import config as flask_config
    if not flask_config.EBAY_CLIENT_ID:
        log.warning("eBay credentials not configured. Set EBAY_CLIENT_ID etc in .env")
        log.info("Skipping eBay order sync — no credentials")
        return

    client = EbayClient()

    try:
        # Get unfulfilled eBay orders
        result = client.get_orders(
            filter_str="orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}",
            limit=50,
        )

        orders = result.get("orders", [])
        if not orders:
            log.info("No new eBay orders")
            return

        conn = get_conn()
        synced = 0

        for ebay_order in orders:
            order_id = ebay_order.get("orderId", "")
            ebay_session_id = f"EBAY-{order_id}"

            # Skip if already synced
            existing = conn.execute(
                "SELECT id FROM orders WHERE stripe_session_id = ?",
                (ebay_session_id,),
            ).fetchone()

            if existing:
                log.debug(f"Order {ebay_session_id} already synced")
                continue

            # Extract order details
            buyer = ebay_order.get("buyer", {})
            checkout = ebay_order.get("buyerCheckoutSummary", {})
            pricing = ebay_order.get("pricingSummary", {})
            fulfillment = ebay_order.get("fulfillmentStartInstruction", [{}])[0]

            email = buyer.get("email", "")
            name = checkout.get("buyerFirstName", "") + " " + checkout.get("buyerLastName", "")
            name = name.strip() or "eBay Buyer"

            # Build address
            ship_to = fulfillment.get("shippingStep", {}).get("shipTo", {})
            address_parts = [
                ship_to.get("fullName", ""),
                ship_to.get("contactAddress", {}).get("addressLine1", ""),
                ship_to.get("contactAddress", {}).get("addressLine2", ""),
                ship_to.get("contactAddress", {}).get("city", ""),
                ship_to.get("contactAddress", {}).get("stateOrProvince", ""),
                ship_to.get("contactAddress", {}).get("postalCode", ""),
                ship_to.get("contactAddress", {}).get("countryCode", ""),
            ]
            address = ", ".join(p for p in address_parts if p)

            # Build items_json from line items
            line_items = ebay_order.get("lineItems", [])
            items = []
            total_cents = 0

            for item in line_items:
                sku = item.get("sku", "")
                # Map eBay SKU back to product slug
                product_slug = sku.replace("RZ-", "") if sku.startswith("RZ-") else sku

                title = item.get("title", "")
                qty = item.get("quantity", 1)
                price = item.get("total", item.get("lineItemCost", {})).get("value", "0")
                price_cents = int(float(price) * 100)

                items.append({
                    "slug": product_slug,
                    "name": title,
                    "qty": qty,
                    "price_cents": price_cents,
                })
                total_cents += price_cents * qty

            # Get totals from pricing summary
            total = pricing.get("total", {}).get("value", "0")
            total_cents = int(float(total) * 100)

            gst = pricing.get("tax", {}).get("value", "0")
            gst_cents = int(float(gst) * 100)

            shipping = pricing.get("deliveryCost", {}).get("shippingCost", {}).get("value", "0")
            shipping_cents = int(float(shipping) * 100)

            if dry_run:
                log.info(f"[DRY RUN] Would sync eBay order {order_id}: {name} ${total_cents/100:.2f}")
                continue

            # Insert into orders table
            try:
                conn.execute(
                    "INSERT INTO orders "
                    "(stripe_session_id, email, name, address, items_json, "
                    "total_cents, gst_cents, shipping_cents, status, source, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'paid', 'ebay', ?, ?)",
                    (
                        ebay_session_id,
                        email,
                        name,
                        address,
                        json.dumps(items),
                        total_cents,
                        gst_cents,
                        shipping_cents,
                        datetime.utcnow().isoformat(),
                        datetime.utcnow().isoformat(),
                    )
                )
                conn.commit()

                # Decrement stock for each item
                for item in items:
                    conn.execute(
                        "UPDATE products SET stock = stock - ? WHERE slug = ? AND stock >= ?",
                        (item["qty"], item["slug"], item["qty"])
                    )
                    # Update inventory batches
                    conn.execute(
                        "UPDATE inventory_batches SET units_sold = units_sold + ? "
                        "WHERE product_slug = ? AND status = 'active' "
                        "ORDER BY created_at DESC LIMIT 1",
                        (item["qty"], item["slug"])
                    )
                conn.commit()

                # Update eBay listing quantities
                for item in line_items:
                    sku = item.get("sku", "")
                    if sku:
                        conn.execute(
                            "UPDATE ebay_listings SET quantity_sold = quantity_sold + ?, "
                            "last_synced_at = ? WHERE sku = ?",
                            (item.get("quantity", 1), datetime.utcnow().isoformat(), sku)
                        )
                conn.commit()

                synced += 1
                log.info(f"Synced eBay order {order_id}: {name} ${total_cents/100:.2f}")

            except Exception as e:
                log.error(f"Error inserting order {order_id}: {e}")
                conn.rollback()

        conn.close()
        log.info(f"Sync complete: {synced} new order(s)")

        # Update eBay listing quantities via API
        if synced > 0:
            _update_listing_quantities(client, conn)

    except Exception as e:
        log.error(f"eBay sync error: {e}")
    finally:
        client.close()


def _update_listing_quantities(client, conn):
    """Update eBay listing quantities after local stock changes."""
    listings = conn.execute(
        "SELECT sku, ebay_offer_id, product_slug FROM ebay_listings "
        "WHERE status = 'active' AND ebay_offer_id != ''"
    ).fetchall()

    for listing in listings:
        product = conn.execute(
            "SELECT stock FROM products WHERE slug = ?", (listing["product_slug"],)
        ).fetchone()

        if product:
            try:
                client.update_offer_quantity(listing["ebay_offer_id"], product["stock"])
                log.info(f"Updated eBay quantity for {listing['sku']}: {product['stock']}")
            except Exception as e:
                log.warning(f"Failed to update eBay qty for {listing['sku']}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Sync eBay orders to RetroZone")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    args = parser.parse_args()

    # Run migration
    add_source_column()

    log.info("Starting eBay order sync...")
    sync_orders(dry_run=args.dry_run)
    log.info("Done")


if __name__ == "__main__":
    main()
