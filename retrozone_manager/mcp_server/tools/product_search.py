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
    """Search AliExpress for retail pricing reference via SearXNG.

    Useful for comparing wholesale (Alibaba) vs retail prices.
    AliExpress is a SPA so direct scraping doesn't work — uses SearXNG search instead.
    """
    import re
    from ..scrapers.base import web_search, web_search_and_read

    # Search for AliExpress listings via SearXNG
    search_text = web_search(f"{query} site:aliexpress.com price", num_results=10)
    results = []

    if search_text:
        blocks = re.split(r'###\s*\d+\.', search_text)[1:]
        for block in blocks:
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
            price_match = re.search(r'US\s*\$\s*([\d,]+\.?\d*)', snippet)
            if not price_match:
                price_match = re.search(r'\$\s*([\d,]+\.?\d*)', snippet)
            if price_match:
                price = float(price_match.group(1).replace(",", ""))

            if title:
                results.append({"title": title[:200], "url": url, "price": price, "snippet": snippet[:150]})

    # Fallback: broader search
    if not results or not any(r["price"] for r in results):
        search_text2 = web_search(f"{query} aliexpress retail price buy", num_results=10)
        if search_text2:
            for block in re.split(r'###\s*\d+\.', search_text2)[1:]:
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
                if title and "aliexpress" not in title.lower() and "aliexpress" not in snippet.lower():
                    continue
                price_match = re.search(r'\$\s*([\d,]+\.?\d*)', snippet)
                price = float(price_match.group(1).replace(",", "")) if price_match else None
                if title:
                    results.append({"title": title[:200], "url": url, "price": price, "snippet": snippet[:150]})

    if not results:
        return (f"No AliExpress results found for '{query}'. "
                f"AliExpress is a SPA — direct scraping is not possible. "
                f"Try search_alibaba for wholesale pricing instead.")

    lines = [f"AliExpress retail results for '{query}':\n"]
    for i, r in enumerate(results[:10], 1):
        price_str = f"${r['price']:.2f}" if r["price"] else "N/A"
        lines.append(f"{i}. {r['title']}\n   Price: {price_str} | {r['url'] or 'N/A'}")

    return "\n\n".join(lines)
