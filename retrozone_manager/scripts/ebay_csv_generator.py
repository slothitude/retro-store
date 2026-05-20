"""eBay CSV listing generator — outputs eBay Seller Hub compatible CSV for bulk upload.

Usage:
    python retrozone_manager/scripts/ebay_csv_generator.py --product r36s-black --dry-run
    python retrozone_manager/scripts/ebay_csv_generator.py --all
    python retrozone_manager/scripts/ebay_csv_generator.py --all --output listings.csv
"""
import csv
import json
import os
import sys
import argparse

# Add parent dirs to path for imports
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from retrozone_manager.mcp_server.db.schema import get_conn
from retrozone_manager.mcp_server.tools.ebay_pricing import calculate_ebay_price

# Add root for pricing module
sys.path.insert(0, ROOT)
from pricing import validate_price

# eBay AU category mapping for retro gaming handhelds
EBAY_CATEGORY_MAP = {
    "handhelds": "139971",   # Video Games & Consoles > Video Game Consoles > Handheld Systems
    "accessories": "43017",  # Video Games & Consoles > Video Game Accessories
    "games": "139973",       # Video Games & Consoles > Video Games
}

# eBay CSV columns for Seller Hub bulk upload
EBAY_CSV_COLUMNS = [
    "*Category",
    "*Title",
    "*Condition",
    "Condition Description",
    "*Price",
    "*Quantity",
    "*Format",
    "*Duration",
    "*ShippingType",
    "*ShippingService-1:Option",
    "*ShippingService-1:Cost",
    "ShippingService-1:FreeShipping",
    "ReturnPolicy",
    "ReturnsAccepted",
    "RefundOption",
    "ReturnsWithin",
    "Description",
    "PicURL",
    "SKU",
    "CustomLabel",
    "ItemSpecifics.Brand",
    "ItemSpecifics.Screen Size",
    "ItemSpecifics.RAM",
    "ItemSpecifics.Storage Capacity",
    "ItemSpecifics.Processor",
    "ItemSpecifics.Color",
]


def build_title(product, max_len=80):
    """Build keyword-optimized eBay title, max 80 chars."""
    name = product["name"]
    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}

    parts = [name]

    # Add key specs to title
    display = specs.get("Display", specs.get("display", ""))
    if display and "IPS" in display:
        parts.append(display.replace('"', '\\"'))

    cpu = specs.get("CPU", specs.get("cpu", ""))
    if cpu:
        parts.append(cpu)

    # Add condition
    parts.append("NEW")

    title = " ".join(parts)
    if len(title) > max_len:
        title = title[:max_len - 3] + "..."

    return title


def build_description(product):
    """Build HTML description for eBay listing."""
    name = product["name"]
    tagline = product.get("tagline", "")
    description = product.get("description", "")
    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}

    specs_rows = ""
    for key, val in specs.items():
        specs_rows += f"<tr><td><b>{key}</b></td><td>{val}</td></tr>"

    html = f"""<div style="font-family: Arial, sans-serif;">
<h2>{name}</h2>
<p><b>{tagline}</b></p>
<p>{description}</p>

<h3>Specifications</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
{specs_rows}
</table>

<h3>Why Buy From RetroMonkey?</h3>
<ul>
<li>Australian seller — fast domestic shipping (2-5 days)</li>
<li>Quality tested before dispatch</li>
<li>12-month Australian warranty</li>
<li>Local support — not 3-6 weeks from China</li>
<li>ABN registered Australian business</li>
</ul>
</div>"""
    return html


def get_condition(product):
    """Map product to eBay condition ID."""
    return "1000"  # New


def generate_csv_row(product, ebay_price_cents=None):
    """Generate a single CSV row dict for a product."""
    if not ebay_price_cents:
        # Get batch cost for pricing
        conn = get_conn()
        batch = conn.execute(
            "SELECT cost_per_unit_cents FROM inventory_batches "
            "WHERE product_slug = ? AND status = 'active' "
            "ORDER BY created_at DESC LIMIT 1",
            (product["slug"],)
        ).fetchone()
        conn.close()

        cost = batch["cost_per_unit_cents"] if batch else product["price_cents"]
        ebay_price_cents = int(product["price_cents"] * 1.05)  # 5% buffer

    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}
    gallery = json.loads(product.get("gallery", "[]")) if product.get("gallery") else []
    image_url = product.get("image", "")

    # eBay needs absolute URLs — prepend site URL to relative paths
    site_url = os.getenv("SITE_URL", "https://retromonkey.ddns.net")
    all_images = [image_url] + gallery if image_url else gallery
    absolute_images = []
    seen = set()
    for img in all_images:
        if img.startswith("http"):
            full = img
        elif img.startswith("/"):
            full = f"{site_url}{img}"
        else:
            continue
        if full not in seen:
            seen.add(full)
            absolute_images.append(full)
    pic_urls = ", ".join(absolute_images)

    return {
        "*Category": EBAY_CATEGORY_MAP.get(product.get("category", "handhelds"), "139971"),
        "*Title": build_title(product),
        "*Condition": get_condition(product),
        "Condition Description": "",
        "*Price": f"{ebay_price_cents / 100:.2f}",
        "*Quantity": str(product.get("stock", 1)),
        "*Format": "FixedPrice",
        "*Duration": "GTC",  # Good 'Til Cancelled
        "*ShippingType": "Flat",
        "*ShippingService-1:Option": "AU_RegularParcelWithSignature",
        "*ShippingService-1:Cost": "8.99",
        "ShippingService-1:FreeShipping": "false",
        "ReturnPolicy": "ReturnsAccepted",
        "ReturnsAccepted": "ReturnsAccepted",
        "RefundOption": "MoneyBack",
        "ReturnsWithin": "Days_30",
        "Description": build_description(product),
        "PicURL": pic_urls,
        "SKU": f"RM-{product['slug']}",
        "CustomLabel": f"RM-{product['slug']}",
        "ItemSpecifics.Brand": specs.get("Brand", "Unbranded"),
        "ItemSpecifics.Screen Size": specs.get("Display", specs.get("Screen Size", "")),
        "ItemSpecifics.RAM": specs.get("RAM", ""),
        "ItemSpecifics.Storage Capacity": specs.get("Storage", specs.get("ROM", "")),
        "ItemSpecifics.Processor": specs.get("CPU", specs.get("Processor", "")),
        "ItemSpecifics.Color": specs.get("Color", specs.get("Colour", "Black")),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate eBay Seller Hub CSV listings")
    parser.add_argument("--product", help="Product slug (e.g. r36s-black)")
    parser.add_argument("--all", action="store_true", help="Generate for all products")
    parser.add_argument("--output", default="ebay_listings.csv", help="Output CSV filename")
    parser.add_argument("--dry-run", action="store_true", help="Print rows without writing file")
    args = parser.parse_args()

    if not args.product and not args.all:
        parser.error("Specify --product <slug> or --all")

    conn = get_conn()

    if args.product:
        product = conn.execute(
            "SELECT * FROM products WHERE slug = ?", (args.product,)
        ).fetchone()
        if not product:
            print(f"Product '{args.product}' not found.")
            conn.close()
            sys.exit(1)
        products = [product]
    else:
        products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()

    conn.close()

    rows = []
    skipped = []
    for p in products:
        p = dict(p)
        ebay_price = int(p["price_cents"] * 1.05)

        # Min-price guard: skip or flag products below minimum
        is_valid, reason = validate_price(p["slug"], ebay_price)
        if not is_valid:
            skipped.append(f"  {p['name']}: {reason}")
            continue  # Skip below-min products

        row = generate_csv_row(p, ebay_price_cents=ebay_price)
        rows.append(row)

    if args.dry_run:
        print(f"=== DRY RUN: {len(rows)} listing(s) ===\n")
        writer = csv.DictWriter(sys.stdout, fieldnames=EBAY_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            # Truncate description for display
            display_row = dict(row)
            if len(display_row.get("Description", "")) > 80:
                display_row["Description"] = display_row["Description"][:80] + "..."
            writer.writerow(display_row)
        print()
    else:
        output_path = os.path.join(ROOT, args.output)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EBAY_CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"Wrote {len(rows)} listing(s) to {output_path}")
        print("Upload via: eBay Seller Hub → Marketing → Bulk listings → Upload CSV")

    # Show pricing summary
    print(f"\n{'='*50}")
    print("Pricing Summary:")
    print(f"{'='*50}")
    for i, p in enumerate(products):
        p = dict(p)
        ebay_price = int(p["price_cents"] * 1.05)
        print(f"  {p['name']}: Web ${p['price_cents']/100:.2f} -> eBay ${ebay_price/100:.2f}")

    if skipped:
        print(f"\n{'='*50}")
        print(f"SKIPPED ({len(skipped)} below min price):")
        print(f"{'='*50}")
        for s in skipped:
            print(s)


if __name__ == "__main__":
    main()
