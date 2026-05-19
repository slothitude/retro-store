"""eBay listing content builder — titles, descriptions, item specifics, category mapping."""
import json


# eBay AU category mapping
CATEGORY_MAP = {
    "handhelds": "139971",   # Video Game Consoles > Handheld Systems
    "accessories": "43017",  # Video Game Accessories
    "games": "139973",       # Video Games
}

DEFAULT_CATEGORY = "139971"

# Keyword templates for SEO-optimized titles
TITLE_TEMPLATE = "{name} {display} {cpu} {storage} Retro Gaming Console NEW"


def build_title(product: dict, max_len: int = 80) -> str:
    """Build a keyword-optimized eBay title (max 80 chars).

    Includes: product name, key specs, condition.
    """
    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}
    name = product["name"]

    parts = [name]

    # Add display spec (common search term)
    display = specs.get("Display", specs.get("display", ""))
    if display:
        parts.append(display.replace('"', "in"))

    # Add CPU/processor
    cpu = specs.get("CPU", specs.get("Processor", ""))
    if cpu:
        parts.append(cpu)

    # Add storage
    storage = specs.get("Storage", specs.get("ROM", specs.get("Storage Capacity", "")))
    if storage:
        parts.append(storage)

    # Add games count or tagline keywords
    tagline = product.get("tagline", "")
    if "game" in tagline.lower():
        parts.append("Games Console")

    parts.append("NEW")

    title = " ".join(parts)
    if len(title) > max_len:
        title = title[:max_len - 3].rsplit(" ", 1)[0] + "..."

    return title


def build_description(product: dict) -> str:
    """Build HTML description for eBay listing.

    Includes: product name, tagline, specs table, value props, warranty info.
    """
    name = product["name"]
    tagline = product.get("tagline", "")
    description = product.get("description", "")
    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}

    specs_rows = ""
    for key, val in specs.items():
        specs_rows += f"<tr><td><b>{key}</b></td><td>{val}</td></tr>\n"

    html = f"""<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
<h2 style="color: #e94560;">{name}</h2>
<p style="font-size: 16px; font-weight: bold;">{tagline}</p>

<p>{description}</p>

<h3 style="color: #e94560; border-bottom: 2px solid #e94560; padding-bottom: 5px;">Specifications</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
<tr style="background: #f5f5f5;"><th>Spec</th><th>Detail</th></tr>
{specs_rows}
</table>

<h3 style="color: #e94560; border-bottom: 2px solid #e94560; padding-bottom: 5px;">Why Buy From RetroZone?</h3>
<ul>
<li><b>Australian Seller</b> — Fast domestic shipping from Australia</li>
<li><b>Quality Tested</b> — Every unit tested before dispatch</li>
<li><b>30-Day Returns</b> — hassle-free return policy</li>
<li><b>Local Support</b> — no waiting weeks for international shipping</li>
<li><b>ABN Registered</b> — legitimate Australian business</li>
</ul>

<h3 style="color: #e94560; border-bottom: 2px solid #e94560; padding-bottom: 5px;">Shipping</h3>
<ul>
<li>Standard: Australia Post tracked (2-5 business days)</li>
<li>Express: Australia Post express (1-2 business days)</li>
<li>All items packed with care in protective packaging</li>
</ul>

<p style="color: #666; font-size: 12px; margin-top: 20px;">
RetroZone — Gaming For Every Australian. ABN provided on request.
</p>
</div>"""
    return html


def build_item_specifics(product: dict) -> dict:
    """Build eBay item specifics dict from product specs.

    Maps product specs to eBay-expected field names.
    """
    specs = json.loads(product.get("specs", "{}")) if product.get("specs") else {}

    specifics = {}

    # Map common product specs to eBay item specifics
    field_map = {
        "Brand": ["Brand", "brand"],
        "MPN": ["MPN", "mpn", "Model"],
        "Screen Size": ["Display", "Screen Size", "Screen", "display"],
        "RAM": ["RAM", "Memory", "ram"],
        "Storage Capacity": ["Storage", "ROM", "Storage Capacity", "storage"],
        "Processor": ["CPU", "Processor", "Chipset", "cpu"],
        "Color": ["Color", "Colour", "color"],
        "Connectivity": ["Connectivity", "WiFi", "connectivity"],
        "Battery": ["Battery", "Battery Life", "battery"],
    }

    for ebay_field, source_keys in field_map.items():
        for key in source_keys:
            if key in specs:
                specifics[ebay_field] = specs[key]
                break

    # Ensure brand is set
    if "Brand" not in specifics:
        specifics["Brand"] = "Unbranded"

    return specifics


def build_category_id(product: dict) -> str:
    """Map product category to eBay AU category ID."""
    category = product.get("category", "handhelds")
    return CATEGORY_MAP.get(category, DEFAULT_CATEGORY)


def build_images(product: dict) -> list:
    """Extract hosted image URLs from product data."""
    image_url = product.get("image", "")
    gallery = json.loads(product.get("gallery", "[]")) if product.get("gallery") else []

    urls = []
    if image_url:
        urls.append(image_url)
    urls.extend(gallery)

    return urls


def build_listing_data(product: dict, price_cents: int = None) -> dict:
    """Build complete listing data dict for eBay API or CSV.

    Combines title, description, specifics, category, images, and pricing.
    """
    if price_cents is None:
        price_cents = int(product.get("price_cents", 0) * 1.05)

    return {
        "sku": f"RZ-{product['slug']}",
        "title": build_title(product),
        "description": build_description(product),
        "item_specifics": build_item_specifics(product),
        "category_id": build_category_id(product),
        "image_urls": build_images(product),
        "condition": "NEW",
        "price_cents": price_cents,
        "quantity": product.get("stock", 1),
        "product_slug": product["slug"],
    }
