"""Product search MCP tools — Alibaba and AliExpress wrappers."""
from ..scrapers.alibaba import search_alibaba as _search_alibaba
from ..scrapers.alibaba import get_alibaba_product_details as _get_details


def search_alibaba(query: str, page: int = 1) -> str:
    """Search Alibaba for wholesale products. Returns products with price/MOQ/supplier/URL.

    Use this to find suppliers and wholesale pricing for products.
    Results include price ranges in USD, minimum order quantities, and supplier info.
    """
    results = _search_alibaba(query, page)
    if not results:
        return "No results found."
    if results and "error" in results[0]:
        return f"Error: {results[0]['error']}"

    lines = [f"Found {len(results)} Alibaba products for '{query}':\n"]
    for i, p in enumerate(results[:15], 1):
        price = p.get("price_raw", "")
        if not price and p.get("price_min_usd"):
            price = f"${p['price_min_usd']:.2f}"
            if p.get("price_max_usd") and p["price_max_usd"] != p["price_min_usd"]:
                price += f" - ${p['price_max_usd']:.2f}"
        lines.append(
            f"{i}. {p['title']}\n"
            f"   Price: {price or 'N/A'} | MOQ: {p.get('moq', 'N/A')}\n"
            f"   Supplier: {p.get('supplier', 'N/A')}\n"
            f"   URL: {p.get('url', 'N/A')}"
        )
    return "\n\n".join(lines)


def get_alibaba_product_details(url: str) -> str:
    """Get detailed info from an Alibaba product page: pricing tiers, specs, shipping, images.

    Pass a product URL from search_alibaba results to get full details.
    """
    result = _get_details(url)
    if "error" in result:
        return f"Error: {result['error']}"

    lines = [f"# {result.get('title', 'Product Details')}\n"]
    lines.append(f"URL: {url}")

    if result.get("price_tiers"):
        lines.append("\nPricing Tiers:")
        for t in result["price_tiers"]:
            lines.append(f"  - {t.get('range', 'N/A')}")

    if result.get("moq"):
        lines.append(f"\nMOQ: {result['moq']}")

    if result.get("shipping"):
        lines.append(f"Shipping: {result['shipping']}")

    if result.get("specs"):
        lines.append("\nSpecs:")
        for k, v in result["specs"].items():
            lines.append(f"  {k}: {v}")

    if result.get("images"):
        lines.append(f"\nImages: {len(result['images'])} found")

    return "\n".join(lines)


def search_aliexpress(query: str, sort: str = "price_asc") -> str:
    """Search AliExpress for retail pricing reference. Useful for comparing wholesale vs retail.

    Sort options: price_asc, price_desc, relevance, newest
    """
    sort_map = {
        "price_asc": "price_asc",
        "price_desc": "price_desc",
        "relevance": "default",
        "newest": "new",
    }
    sort_param = sort_map.get(sort, "price_asc")

    from ..scrapers.base import fetch_html_smart
    url = f"https://www.aliexpress.com/glo/search?SearchText={query}&SortType={sort_param}"

    html = fetch_html_smart(url, timeout=30)
    if html.startswith("FETCH_ERROR:"):
        return f"Error fetching AliExpress: {html}. Consider using the Alibaba search instead for supplier pricing."

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    results = []
    # Try JSON-LD first (AliExpress is SPA-heavy)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
            items = data.get("itemListElement", [])
            for item in items[:10]:
                prod = item.get("item", {})
                if prod.get("name"):
                    results.append({
                        "title": prod["name"],
                        "url": prod.get("url", ""),
                        "price": prod.get("offers", {}).get("price", "N/A"),
                    })
        except Exception:
            continue

    if not results:
        return f"A no results found on AliExpress for '{query}'. Note: AliExpress is a SPA — web scraping may be limited. Consider using the Alibaba search instead for supplier pricing."

    lines = [f"AliExpress results for '{query}' ({sort}):\n"]
    for i, r in enumerate(results[:10], 1):
        lines.append(f"{i}. {r['title']}\n   Price: {r['price']} | {r.get('url', 'N/A')}")

    return "\n\n".join(lines)


import json
