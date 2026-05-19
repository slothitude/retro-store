"""eBay pricing calculator — compare channel margins and recommend eBay prices."""
from ..db.schema import get_conn

# AU eBay free tier: no insertion fee for first 250 listings/mo
EBAY_FEE_RATE = 0.0
EBAY_SHIPPING_COST_CENTS = 899  # $8.99 AusPost standard


def calculate_ebay_price(cost_cents: int, fee_rate: float = EBAY_FEE_RATE,
                         shipping_cents: int = EBAY_SHIPPING_COST_CENTS) -> int:
    """Calculate recommended eBay price from cost. Returns price in cents.

    Uses the store's standard 1.40x margin, plus 5% buffer for fee changes.
    Shipping is separate (buyer-paid or included).
    """
    retail = int(cost_cents * 1.40)
    with_buffer = int(retail * 1.05)

    # If there's a fee, ensure price covers it
    if fee_rate > 0:
        fee_amount = int(with_buffer * fee_rate)
        with_buffer += fee_amount

    return with_buffer


def compare_channel_pricing(product_slug: str) -> str:
    """Compare web store price vs calculated eBay price vs market data.

    Returns a formatted text summary.
    """
    conn = get_conn()
    try:
        # Get product
        product = conn.execute(
            "SELECT * FROM products WHERE slug = ?", (product_slug,)
        ).fetchone()
        if not product:
            return f"Product '{product_slug}' not found."

        # Get latest batch cost
        batch = conn.execute(
            "SELECT cost_per_unit_cents FROM inventory_batches "
            "WHERE product_slug = ? AND status = 'active' "
            "ORDER BY created_at DESC LIMIT 1",
            (product_slug,)
        ).fetchone()
        cost_cents = batch["cost_per_unit_cents"] if batch else 0

        web_price = product["price_cents"]
        ebay_price = calculate_ebay_price(cost_cents) if cost_cents else 0

        # Get recent eBay market data
        market = conn.execute(
            "SELECT results_json, checked_at FROM price_checks "
            "WHERE product_slug = ? AND source = 'ebay' "
            "ORDER BY checked_at DESC LIMIT 3",
            (product_slug,)
        ).fetchall()

        lines = [
            f"Channel Pricing for {product['name']} ({product_slug}):\n",
            f"  Web Store: ${web_price / 100:.2f}",
            f"  Batch Cost: ${cost_cents / 100:.2f}" if cost_cents else "  Batch Cost: N/A (no active batch)",
            f"  eBay Recommended: ${ebay_price / 100:.2f}" if ebay_price else "  eBay Recommended: N/A",
        ]

        if web_price and ebay_price:
            diff = ebay_price - web_price
            lines.append(f"  Price Diff: ${diff / 100:+.2f} (eBay vs web)")

        if market:
            import json
            lines.append(f"\n  eBay Market Data ({len(market)} recent checks):")
            for m in market:
                try:
                    data = json.loads(m["results_json"])
                    avg = data.get("avg_sold_price_cents", 0)
                    low = data.get("min_sold_price_cents", 0)
                    high = data.get("max_sold_price_cents", 0)
                    lines.append(
                        f"    {m['checked_at'][:10]}: "
                        f"avg ${avg / 100:.2f}, range ${low / 100:.2f}-${high / 100:.2f}"
                    )
                except (json.JSONDecodeError, TypeError):
                    lines.append(f"    {m['checked_at'][:10]}: (parse error)")
        else:
            lines.append("\n  No eBay market data yet. Run Price Monitor workflow first.")

        # Margin analysis
        if cost_cents and ebay_price:
            ebay_margin = (ebay_price - cost_cents) / ebay_price * 100
            web_margin = (web_price - cost_cents) / web_price * 100
            lines.append(f"\n  Margins:")
            lines.append(f"    Web: {web_margin:.1f}%")
            lines.append(f"    eBay: {ebay_margin:.1f}%")

        return "\n".join(lines)
    finally:
        conn.close()
