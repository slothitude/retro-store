"""Alibaba search + detail scraper.

Strategy chain:
1. Try direct httpx fetch
2. Try web-reader MCP (Playwright with anti-detection)
3. Try SearXNG general search for wholesale pricing data
"""
import re
from bs4 import BeautifulSoup
from .base import fetch_html_smart, web_search


def search_alibaba(query: str, page: int = 1) -> list[dict]:
    """Search Alibaba for products. Returns list of product dicts."""
    url = f"https://www.alibaba.com/trade/search?SearchText={query}&page={page}"

    try:
        html = fetch_html_smart(url, timeout=30)
    except Exception:
        html = ""

    if html and not html.startswith("FETCH_ERROR:"):
        products = _parse_alibaba_html(html)
        if products:
            return products

    # Fallback: SearXNG search
    return _search_alibaba_via_searxng(query)


def _parse_alibaba_html(html: str) -> list[dict]:
    """Parse Alibaba search results HTML."""
    soup = BeautifulSoup(html, "lxml")
    products = []

    cards = soup.select('[class*="organic-gallery"] [class*="card-"]')
    if not cards:
        cards = soup.select('[data-spm="productCard"]')
    if not cards:
        cards = soup.select('.J-II-card')

    for card in cards[:20]:
        try:
            product = _parse_card(card)
            if product.get("title"):
                products.append(product)
        except Exception:
            continue

    if not products:
        products = _fallback_parse(soup)

    return products


def _parse_card(card) -> dict:
    title_el = card.select_one('[class*="title"]') or card.select_one("a[href]")
    title = title_el.get_text(strip=True) if title_el else ""

    link = ""
    a_tag = card.select_one("a[href]")
    if a_tag:
        href = a_tag.get("href", "")
        if href.startswith("/"):
            link = f"https://www.alibaba.com{href}"
        elif href.startswith("http"):
            link = href

    price_text = ""
    price_el = card.select_one('[class*="price"]') or card.select_one('[class*="Price"]')
    if price_el:
        price_text = price_el.get_text(strip=True)

    price_min, price_max = _parse_price_range(price_text)

    moq_text = ""
    moq_el = card.select_one('[class*="moq"]') or card.select_one('[class*="min-order"]')
    if moq_el:
        moq_text = moq_el.get_text(strip=True)

    supplier = ""
    supplier_el = card.select_one('[class*="store"]') or card.select_one('[class*="supplier"]')
    if supplier_el:
        supplier = supplier_el.get_text(strip=True)

    img_url = ""
    img_el = card.select_one("img")
    if img_el:
        img_url = img_el.get("src", "") or img_el.get("data-src", "")

    return {
        "title": title[:200],
        "url": link,
        "price_min_usd": price_min,
        "price_max_usd": price_max,
        "price_raw": price_text,
        "moq": moq_text,
        "supplier": supplier,
        "image": img_url,
    }


def _parse_price_range(text: str) -> tuple:
    if not text:
        return None, None
    nums = re.findall(r'[\d]+\.?\d*', text)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    elif len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return None, None


def _fallback_parse(soup: BeautifulSoup) -> list[dict]:
    import json
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
            items = data.get("itemListElement", [])
            for item in items[:15]:
                prod = item.get("item", {})
                if prod.get("name"):
                    products.append({
                        "title": prod.get("name", ""),
                        "url": prod.get("url", ""),
                        "price_min_usd": None,
                        "price_max_usd": None,
                        "price_raw": prod.get("offers", {}).get("price", ""),
                        "moq": "",
                        "supplier": "",
                        "image": prod.get("image", ""),
                    })
        except Exception:
            continue
    return products


def _search_alibaba_via_searxng(query: str) -> list[dict]:
    """Fallback: search for wholesale pricing via SearXNG."""
    from .base import web_search_and_read

    # Query 1: Specific Alibaba search
    search_text = web_search(f"{query} wholesale site:alibaba.com", num_results=10)
    products = []

    if search_text:
        for block in re.split(r'###\s*\d+\.', search_text)[1:]:
            try:
                product = _parse_searxng_product_block(block)
                if product.get("title"):
                    products.append(product)
            except Exception:
                continue

    # Query 2: Broader wholesale search
    if not products or not any(p.get("price_min_usd") for p in products):
        search_text2 = web_search(f"{query} wholesale price MOQ buy bulk", num_results=10)
        if search_text2:
            for block in re.split(r'###\s*\d+\.', search_text2)[1:]:
                try:
                    product = _parse_searxng_product_block(block)
                    if product.get("title"):
                        products.append(product)
                except Exception:
                    continue

    # Query 3: If still no priced results, try search_and_read
    priced = [p for p in products if p.get("price_min_usd")]
    if not priced:
        read_text = web_search_and_read(f"{query} wholesale price", num_results=3)
        if read_text and len(read_text) > 200:
            prices_found = re.findall(r'US\s*\$\s*([\d,]+\.?\d*)', read_text)
            if not prices_found:
                prices_found = re.findall(r'\$\s*([\d,]+\.?\d*)', read_text)
            if prices_found:
                price_vals = [float(p.replace(",", "")) for p in prices_found[:10]]
                products.insert(0, {
                    "title": f"Wholesale pricing for '{query}' (multiple sources)",
                    "url": "",
                    "price_min_usd": min(price_vals),
                    "price_max_usd": max(price_vals),
                    "price_raw": f"${min(price_vals):.2f} - ${max(price_vals):.2f}",
                    "moq": "",
                    "supplier": "",
                    "image": "",
                })

    if not products:
        return [{"error": f"No Alibaba results found for '{query}'. "
                          f"Direct fetch blocked and SearXNG returned no results."}]

    return products


def _parse_searxng_product_block(block: str) -> dict:
    """Parse a SearXNG search result block into a product dict."""
    lines = block.strip().split("\n")
    title = lines[0].strip() if lines else ""
    url = ""
    snippet = ""

    for line in lines[1:]:
        line = line.strip()
        if line.startswith("**URL:**"):
            url = line.replace("**URL:**", "").strip()
        elif line.startswith(">"):
            snippet += line[1:].strip() + " "

    # Extract price (USD preferred)
    price_min, price_max = None, None
    price_match = re.search(r'US\s*\$\s*([\d,]+\.?\d*)', snippet)
    if price_match:
        price_min = float(price_match.group(1).replace(",", ""))
        price_max = price_min
    else:
        # Try generic $ - may be USD for wholesale
        price_match = re.search(r'\$\s*([\d,]+\.?\d*)', snippet)
        if price_match:
            val = float(price_match.group(1).replace(",", ""))
            if 0.5 <= val <= 9999:
                price_min = val
                price_max = val

    # Extract MOQ
    moq = ""
    moq_match = re.search(r'(\d+)\s*(?:Pieces?|pcs|units?)', snippet, re.IGNORECASE)
    if moq_match:
        moq = f"{moq_match.group(1)} Pieces"

    return {
        "title": title[:200],
        "url": url,
        "price_min_usd": price_min,
        "price_max_usd": price_max,
        "price_raw": f"US ${price_min}" if price_min else "",
        "moq": moq,
        "supplier": "",
        "image": "",
    }


def get_alibaba_product_details(url: str) -> dict:
    """Scrape an Alibaba product detail page for pricing tiers, specs, shipping."""
    try:
        html = fetch_html_smart(url, timeout=30)
        if html.startswith("FETCH_ERROR:"):
            return {"error": html}
    except Exception as e:
        return {"error": f"Failed to fetch product page: {e}"}

    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_el = soup.select_one("h1") or soup.select_one('[class*="product-name"]')
    if title_el:
        title = title_el.get_text(strip=True)

    price_tiers = []
    price_section = soup.select_one('[class*="price"]') or soup.select_one('[class*="Price"]')
    if price_section:
        price_text = price_section.get_text(strip=True)
        price_tiers.append({"range": price_text})

    specs = {}
    for row in soup.select("table tr, [class*='attribute'] [class*='item']"):
        cells = row.select("td, th")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            if key and val:
                specs[key] = val

    moq = ""
    moq_el = soup.select_one('[class*="moq"]') or soup.select_one('[class*="min-order"]')
    if moq_el:
        moq = moq_el.get_text(strip=True)

    shipping = ""
    ship_el = soup.select_one('[class*="shipping"]') or soup.select_one('[class*="delivery"]')
    if ship_el:
        shipping = ship_el.get_text(strip=True)[:200]

    images = []
    for img in soup.select('[class*="image"] img, [class*="gallery"] img')[:5]:
        src = img.get("src", "") or img.get("data-src", "")
        if src:
            images.append(src)

    return {
        "title": title,
        "url": url,
        "price_tiers": price_tiers,
        "specs": specs,
        "moq": moq,
        "shipping": shipping,
        "images": images,
    }
