"""eBay sold/active listings scraper.

Strategy chain:
1. Try direct httpx fetch (usually 403 but worth trying)
2. Try SearXNG general search to find eBay listing URLs
3. Try SearXNG with broader product queries for price data
4. Try web-reader MCP read_url on individual eBay listing pages
"""
import re
from bs4 import BeautifulSoup
from .base import fetch_html_fallback, web_search, fetch_via_web_reader


def search_ebay_sold(query: str, marketplace: str = "ebay.com.au") -> list[dict]:
    """Search eBay sold listings. Returns what items actually sold for (AUD)."""
    # Strategy 1: Direct fetch
    url = (
        f"https://www.{marketplace}/sch/i.html?"
        f"_nkw={query.replace(' ', '+')}"
        f"&LH_Sold=1&LH_Complete=1"
        f"&_sop=12"
    )
    html = fetch_html_fallback(url, timeout=30)
    if not html.startswith("FETCH_ERROR:"):
        results = _parse_ebay_listings(html, "sold")
        if results:
            return results

    # Strategy 2: SearXNG search for eBay listings
    return _search_ebay_via_searxng(query, marketplace, "sold")


def search_ebay_active(query: str, marketplace: str = "ebay.com.au") -> list[dict]:
    """Search eBay active listings. Returns current competitor asking prices."""
    url = (
        f"https://www.{marketplace}/sch/i.html?"
        f"_nkw={query.replace(' ', '+')}"
        f"&_sop=15"
    )
    html = fetch_html_fallback(url, timeout=30)
    if not html.startswith("FETCH_ERROR:"):
        results = _parse_ebay_listings(html, "active")
        if results:
            return results

    return _search_ebay_via_searxng(query, marketplace, "active")


def _search_ebay_via_searxng(query: str, marketplace: str, listing_type: str) -> list[dict]:
    """Use SearXNG to find eBay listings with pricing info.

    Tries multiple query strategies:
    1. Site-restricted search (finds actual eBay listing URLs)
    2. Broader product search (finds prices from any source)
    3. If URLs found but no prices, read individual eBay pages via web-reader
    """
    from .base import web_search_and_read

    listings = []
    seen_urls = set()

    # Query 1: Site-restricted search for actual eBay listings
    site = marketplace.split(".")[-2] + "." + marketplace.split(".")[-1]  # ebay.com.au
    site_query = f"{query} site:{site}"
    search_text = web_search(site_query, num_results=15)
    if search_text:
        for block in _split_search_results(search_text):
            try:
                listing = _parse_search_block(block, listing_type)
                if listing.get("title") and listing["url"] not in seen_urls:
                    seen_urls.add(listing["url"])
                    listings.append(listing)
            except Exception:
                continue

    # Query 2: Broader search for price comparison data
    if listing_type == "sold":
        price_query = f"{query} sold price australia"
    else:
        price_query = f"{query} buy now price australia"
    search_text2 = web_search(price_query, num_results=10)
    if search_text2:
        for block in _split_search_results(search_text2):
            try:
                listing = _parse_search_block(block, listing_type)
                if listing.get("title") and listing["url"] not in seen_urls:
                    seen_urls.add(listing["url"])
                    listings.append(listing)
            except Exception:
                continue

    # Strategy 3: If we have eBay URLs but no prices, read individual pages
    ebay_urls_without_price = [
        l for l in listings
        if not l.get("price") and "ebay." in l.get("url", "")
    ]
    if ebay_urls_without_price and len(ebay_urls_without_price) <= 3:
        for listing in ebay_urls_without_price:
            page_html = fetch_via_web_reader(listing["url"])
            if page_html and not page_html.startswith("FETCH_ERROR:"):
                price_data = _extract_price_from_item_page(page_html)
                if price_data.get("price"):
                    listing["price"] = price_data["price"]
                    listing["currency"] = price_data.get("currency", "AUD")
                    listing["condition"] = price_data.get("condition", "")
                    listing["shipping"] = price_data.get("shipping", "")

    # Strategy 4: If still no priced results, try search_and_read for deeper content
    priced = [l for l in listings if l.get("price") is not None]
    if not priced:
        read_text = web_search_and_read(f"{query} price ebay australia", num_results=3)
        if read_text and len(read_text) > 200:
            prices_found = re.findall(
                r'(?:AU\s*\$|A\$|\$)\s*([\d,]+\.?\d*)', read_text
            )
            if prices_found:
                price_vals = [float(p.replace(",", "")) for p in prices_found[:10]]
                listings.insert(0, {
                    "title": f"Market price research for '{query}' (multiple sources)",
                    "url": "",
                    "price": min(price_vals),
                    "currency": "AUD",
                    "shipping": "",
                    "condition": "",
                    "sold_info": (
                        f"Price range: ${min(price_vals):.2f} - ${max(price_vals):.2f} AUD "
                        f"across {len(price_vals)} sources. {read_text[:200]}"
                    ),
                    "image": "",
                    "type": listing_type,
                })

    if not listings:
        return [{"error": f"No eBay {listing_type} results found for '{query}'. "
                          f"SearXNG engines may be temporarily rate-limited."}]

    return listings


def _split_search_results(text: str) -> list[str]:
    """Split SearXNG markdown results into individual blocks."""
    return re.split(r'###\s*\d+\.', text)[1:]


def _parse_search_block(block: str, listing_type: str) -> dict:
    """Parse a search result block into a listing dict."""
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

    price = None
    currency = "AUD"

    # Try AU$ first
    price_match = re.search(r'AU\s*\$\s*([\d,]+\.?\d*)', snippet)
    if price_match:
        price = float(price_match.group(1).replace(",", ""))
        currency = "AUD"
    else:
        price_match = re.search(r'US\s*\$\s*([\d,]+\.?\d*)', snippet)
        if price_match:
            price = float(price_match.group(1).replace(",", ""))
            currency = "USD"
        else:
            # Also check title for price
            combined = title + " " + snippet
            price_match = re.search(r'\$\s*([\d,]+\.?\d*)', combined)
            if price_match:
                val = float(price_match.group(1).replace(",", ""))
                # Filter out obviously wrong prices (< $1 or > $10000 for typical items)
                if 1 <= val <= 9999:
                    price = val

    # Mark if this is an eBay result
    is_ebay = "ebay." in url or "ebay" in snippet.lower()

    return {
        "title": title[:200],
        "url": url,
        "price": price,
        "currency": currency,
        "shipping": "",
        "condition": "",
        "sold_info": snippet[:300],
        "image": "",
        "type": listing_type,
    }


def _extract_price_from_item_page(html: str) -> dict:
    """Extract price, condition, shipping from an eBay item page."""
    soup = BeautifulSoup(html, "lxml")
    result = {}

    # Price - try multiple selectors
    price_el = (
        soup.select_one('[data-testid="x-price-primary"]')
        or soup.select_one('[class*="x-price-primary"]')
        or soup.select_one('#prcIsum')
        or soup.select_one('[itemprop="price"]')
        or soup.select_one('[class*="notranslate"]')
    )
    if price_el:
        price_text = price_el.get("content") or price_el.get_text(strip=True)
        nums = re.findall(r'[\d,]+\.?\d*', price_text)
        if nums:
            result["price"] = float(nums[0].replace(",", ""))
        if "US" in price_text or "USD" in price_text:
            result["currency"] = "USD"
        else:
            result["currency"] = "AUD"

    # Condition
    cond_el = soup.select_one('#vi-itm-cond') or soup.select_one('[data-testid="x-item-condition"]')
    if cond_el:
        result["condition"] = cond_el.get_text(strip=True)

    # Shipping
    ship_el = soup.select_one('#shSummary') or soup.select_one('[class*="shipping"]')
    if ship_el:
        result["shipping"] = ship_el.get_text(strip=True)[:100]

    return result


def _parse_ebay_listings(html: str, listing_type: str) -> list[dict]:
    """Parse eBay search results HTML page."""
    soup = BeautifulSoup(html, "lxml")
    listings = []

    items = soup.select('li[class*="s-item"]')
    if not items:
        items = soup.select('[class*="srp-results"] li')
    if not items:
        items = soup.select('#ListViewInner li')

    for item in items[:25]:
        try:
            listing = _parse_listing_card(item, listing_type)
            if listing.get("title"):
                listings.append(listing)
        except Exception:
            continue

    return listings


def _parse_listing_card(item, listing_type: str) -> dict:
    """Parse a single eBay listing card from HTML."""
    title = ""
    title_el = item.select_one('[class*="s-item__title"]') or item.select_one("h3")
    if title_el:
        title = title_el.get_text(strip=True)
    if title.lower().startswith("shop on ebay"):
        return {}

    url = ""
    link_el = item.select_one("a[href]")
    if link_el:
        url = link_el.get("href", "").split("?")[0]

    price = None
    currency = "AUD"
    price_el = item.select_one('[class*="s-item__price"]') or item.select_one('[class*="price"]')
    if price_el:
        price_text = price_el.get_text(strip=True)
        nums = re.findall(r'[\d]+\.?\d*', price_text)
        if nums:
            price = float(nums[0])
        if "US" in price_text or "USD" in price_text:
            currency = "USD"

    shipping = ""
    ship_el = item.select_one('[class*="s-item__shipping"]') or item.select_one('[class*="logistics"]')
    if ship_el:
        shipping = ship_el.get_text(strip=True)

    sold_info = ""
    sold_el = item.select_one('[class*="s-item__additional"]') or item.select_one('[class*="s-item__hotness"]')
    if sold_el:
        sold_info = sold_el.get_text(strip=True)

    condition = ""
    cond_el = item.select_one('[class*="s-item__condition"]') or item.select_one('[class*="condition"]')
    if cond_el:
        condition = cond_el.get_text(strip=True)

    image = ""
    img_el = item.select_one("img")
    if img_el:
        image = img_el.get("src", "") or img_el.get("data-src", "")

    return {
        "title": title[:200],
        "url": url,
        "price": price,
        "currency": currency,
        "shipping": shipping,
        "condition": condition,
        "sold_info": sold_info,
        "image": image,
        "type": listing_type,
    }
