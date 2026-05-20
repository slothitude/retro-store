"""Minimum price guard — never sell at a loss.

Single source of truth for margin calculations. Accounts for:
- Product cost (batch or estimated)
- Packaging ($1.35)
- Outbound shipping ($8.50)
- Stripe fees (1.75% + $0.30)
- GST (10% inclusive)

Formula: min_price = (cost + packaging + shipping + stripe_fixed) / (1 - stripe_pct - gst_rate)
Rounds UP to ensure full coverage.
"""
import math
from db import get_db


# Default cost parameters (can be overridden per-product via product_cost_profiles)
DEFAULTS = {
    "packaging_cents": 135,
    "shipping_out_cents": 850,
    "stripe_percent_bps": 175,   # 1.75%
    "stripe_fixed_cents": 30,
    "gst_rate_bps": 909,         # ~9.09% of GST-inclusive price (= 10% of pre-GST)
}

# Enforcement mode: "warn" logs violations, "enforce" blocks them
PRICING_ENFORCEMENT = "warn"


def _get_cost_params(slug=None):
    """Get cost parameters, with per-product overrides if set."""
    params = dict(DEFAULTS)
    if slug:
        conn = get_db()
        override = conn.execute(
            "SELECT packaging_cents, shipping_out_cents, override_min_price, notes "
            "FROM product_cost_profiles WHERE slug = ?",
            (slug,)
        ).fetchone()
        conn.close()
        if override:
            if override["packaging_cents"]:
                params["packaging_cents"] = override["packaging_cents"]
            if override["shipping_out_cents"]:
                params["shipping_out_cents"] = override["shipping_out_cents"]
            if override["override_min_price"]:
                params["override_min_price"] = override["override_min_price"]
    return params


def calculate_min_price(cost_cents, slug=None):
    """Calculate the minimum profitable price in cents for a given cost.

    Returns the price that covers: cost + packaging + shipping + Stripe fees + GST.
    Formula: (cost + packaging + shipping + stripe_fixed) / (1 - stripe_pct - gst_rate)
    Always rounds UP.
    """
    if cost_cents <= 0:
        return 0

    params = _get_cost_params(slug)

    # Check for hard override
    if "override_min_price" in params and params["override_min_price"]:
        return params["override_min_price"]

    packaging = params["packaging_cents"]
    shipping = params["shipping_out_cents"]
    stripe_pct = params["stripe_percent_bps"] / 10000  # bps → decimal
    stripe_fixed = params["stripe_fixed_cents"]
    gst_rate = params["gst_rate_bps"] / 10000  # bps → decimal

    numerator = cost_cents + packaging + shipping + stripe_fixed
    denominator = 1 - stripe_pct - gst_rate

    if denominator <= 0:
        # Fees exceed 100% — impossible to profit
        return cost_cents + packaging + shipping + stripe_fixed + 1

    min_price = math.ceil(numerator / denominator)
    return min_price


def calculate_product_min_price(slug):
    """Get full min-price breakdown for a product.

    Looks up active batch cost, falls back to estimated_cost_cents.
    Returns dict: {min_price, cost_cents, packaging, shipping, stripe_fees, gst, margin_cents}
    """
    conn = get_db()
    product = conn.execute(
        "SELECT price_cents, estimated_cost_cents, min_price_cents FROM products WHERE slug = ?",
        (slug,)
    ).fetchone()

    if not product:
        conn.close()
        return None

    # Get cost: active batch > estimated > 0
    batch = conn.execute(
        "SELECT cost_per_unit_cents FROM inventory_batches "
        "WHERE product_slug = ? AND status = 'active' "
        "ORDER BY created_at DESC LIMIT 1",
        (slug,)
    ).fetchone()
    conn.close()

    cost_cents = 0
    cost_source = "none"
    if batch and batch["cost_per_unit_cents"] > 0:
        cost_cents = batch["cost_per_unit_cents"]
        cost_source = "batch"
    elif product["estimated_cost_cents"] > 0:
        cost_cents = product["estimated_cost_cents"]
        cost_source = "estimated"

    params = _get_cost_params(slug)
    packaging = params["packaging_cents"]
    shipping = params["shipping_out_cents"]
    stripe_pct = params["stripe_percent_bps"] / 10000
    stripe_fixed = params["stripe_fixed_cents"]
    gst_rate = params["gst_rate_bps"] / 10000

    min_price = calculate_min_price(cost_cents, slug)

    # Calculate fees at min_price
    stripe_fees = round(min_price * stripe_pct) + stripe_fixed
    gst_amount = round(min_price * gst_rate)

    return {
        "min_price_cents": min_price,
        "cost_cents": cost_cents,
        "cost_source": cost_source,
        "packaging_cents": packaging,
        "shipping_cents": shipping,
        "stripe_fees_cents": stripe_fees,
        "gst_cents": gst_amount,
        "current_price_cents": product["price_cents"],
        "stored_min_price_cents": product["min_price_cents"] or 0,
    }


def validate_price(slug, price_cents):
    """Check if a price is above the minimum profitable price.

    Returns (is_valid, reason_string).
    """
    breakdown = calculate_product_min_price(slug)
    if not breakdown:
        return True, "Product not found — skipping validation"

    if breakdown["cost_cents"] == 0:
        return True, "No cost data — cannot validate"

    min_price = breakdown["min_price_cents"]
    if price_cents < min_price:
        return False, (
            f"Price ${price_cents/100:.2f} is below minimum ${min_price/100:.2f}. "
            f"Cost: ${breakdown['cost_cents']/100:.2f}, "
            f"Fees (pkg+ship+stripe+gst): ${(min_price - breakdown['cost_cents'])/100:.2f}"
        )

    return True, f"OK — ${price_cents/100:.2f} covers min ${min_price/100:.2f}"


def get_margin_health(slug):
    """Get margin health indicator: green (>20%), yellow (10-20%), red (<10%), danger (below min), no_data.

    Returns dict: {health, margin_pct, current_price, min_price, cost}
    """
    conn = get_db()
    product = conn.execute(
        "SELECT price_cents, estimated_cost_cents FROM products WHERE slug = ?",
        (slug,)
    ).fetchone()
    conn.close()

    if not product:
        return {"health": "no_data", "margin_pct": 0, "current_price": 0, "min_price": 0, "cost": 0}

    breakdown = calculate_product_min_price(slug)
    if not breakdown or breakdown["cost_cents"] == 0:
        return {
            "health": "no_data",
            "margin_pct": 0,
            "current_price": product["price_cents"],
            "min_price": 0,
            "cost": 0,
        }

    current = product["price_cents"]
    min_price = breakdown["min_price_cents"]
    cost = breakdown["cost_cents"]

    if current < min_price:
        health = "danger"
    else:
        margin_pct = ((current - cost) / cost * 100) if cost > 0 else 0
        if margin_pct > 20:
            health = "green"
        elif margin_pct > 10:
            health = "yellow"
        else:
            health = "red"

    margin_pct = ((current - cost) / cost * 100) if cost > 0 else 0
    return {
        "health": health,
        "margin_pct": round(margin_pct, 1),
        "current_price": current,
        "min_price": min_price,
        "cost": cost,
    }


def recalculate_all_min_prices():
    """Iterate all products and update min_price_cents column. Returns count updated."""
    conn = get_db()
    products = conn.execute("SELECT slug FROM products").fetchall()
    updated = 0
    for p in products:
        breakdown = calculate_product_min_price(p["slug"])
        if breakdown and breakdown["cost_cents"] > 0:
            conn.execute(
                "UPDATE products SET min_price_cents = ? WHERE slug = ?",
                (breakdown["min_price_cents"], p["slug"])
            )
            updated += 1
    conn.commit()
    conn.close()
    return updated
