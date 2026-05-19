"""Scheduled price monitor — checks eBay prices for store products and logs to DB.

Run manually:
    python retrozone_manager/scripts/price_monitor.py
    python retrozone_manager/scripts/price_monitor.py --product r36s-retro-handheld

Run via Windows Task Scheduler (recommended: every 6 hours).

Uses the same SearXNG fallback chain as the MCP scrapers. Results are stored
in the price_checks table for the Suppliers panel to display trends.
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime

# Ensure retro-store root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from retrozone_manager.db_layer import StoreDB
from retrozone_manager.mcp_server.db.schema import get_conn
from retrozone_manager.mcp_server.scrapers.ebay import search_ebay_sold, search_ebay_active

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "price_monitor.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("price_monitor")


def run_check(product_slug: str = None):
    """Run price checks for all products (or a single product)."""
    db = StoreDB()
    products = db.get_products()

    if product_slug:
        products = [p for p in products if p["slug"] == product_slug]
        if not products:
            log.error(f"Product '{product_slug}' not found")
            return

    conn = get_conn()
    checked = 0
    errors = 0

    for product in products:
        name = product["name"]
        slug = product["slug"]
        log.info(f"Checking prices for {name} ({slug})...")

        # Search eBay sold listings
        try:
            sold_results = search_ebay_sold(name)
            sold_data = sold_results if isinstance(sold_results, list) else []
            if sold_data and "error" in sold_data[0]:
                sold_data = []
                log.warning(f"  eBay sold error for {name}: {sold_results[0].get('error', '')[:100]}")
        except Exception as e:
            sold_data = []
            log.warning(f"  eBay sold exception for {name}: {e}")

        # Search eBay active listings
        try:
            active_results = search_ebay_active(name)
            active_data = active_results if isinstance(active_results, list) else []
            if active_data and "error" in active_data[0]:
                active_data = []
                log.warning(f"  eBay active error for {name}: {active_results[0].get('error', '')[:100]}")
        except Exception as e:
            active_data = []
            log.warning(f"  eBay active exception for {name}: {e}")

        # Extract summary stats
        sold_prices = [r["price"] for r in sold_data if r.get("price") is not None]
        active_prices = [r["price"] for r in active_data if r.get("price") is not None]

        result = {
            "product_name": name,
            "our_price_cents": product["price_cents"],
            "ebay_sold": {
                "count": len(sold_data),
                "avg_price": round(sum(sold_prices) / len(sold_prices), 2) if sold_prices else None,
                "min_price": round(min(sold_prices), 2) if sold_prices else None,
                "max_price": round(max(sold_prices), 2) if sold_prices else None,
            },
            "ebay_active": {
                "count": len(active_data),
                "avg_price": round(sum(active_prices) / len(active_prices), 2) if active_prices else None,
                "min_price": round(min(active_prices), 2) if active_prices else None,
                "max_price": round(max(active_prices), 2) if active_prices else None,
            },
        }

        # Save to price_checks table
        try:
            conn.execute(
                "INSERT INTO price_checks (product_slug, source, query, results_json, checked_at) VALUES (?, ?, ?, ?, ?)",
                (slug, "ebay", name, json.dumps(result), datetime.now(datetime.UTC).isoformat()),
            )
            conn.commit()
            checked += 1
            log.info(
                f"  Saved: {len(sold_data)} sold, {len(active_data)} active listings"
                f"{f' | Sold avg: ${sum(sold_prices)/len(sold_prices):.2f}' if sold_prices else ''}"
            )
        except Exception as e:
            errors += 1
            log.error(f"  DB error saving results for {slug}: {e}")

    conn.close()
    log.info(f"Done: {checked} products checked, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Price monitor — check competitor eBay pricing")
    parser.add_argument("--product", help="Check a single product by slug")
    args = parser.parse_args()
    run_check(args.product)
