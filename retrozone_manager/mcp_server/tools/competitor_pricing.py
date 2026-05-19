"""Competitor pricing MCP tools — eBay sold/active listing wrappers."""
from ..scrapers.ebay import search_ebay_sold as _search_sold
from ..scrapers.ebay import search_ebay_active as _search_active


def search_ebay_sold(query: str, marketplace: str = "ebay.com.au") -> str:
    """Search eBay completed/sold listings to see what items ACTUALLY sold for.

    Use this to check real market prices — what customers are paying, not what sellers are asking.
    Returns AUD prices from ebay.com.au by default.

    NOTE: eBay blocks automated scraping. For best results in Connected mode,
    also use mcp__web-reader__read_url or mcp__web-reader__web_search directly.
    """
    results = _search_sold(query, marketplace)
    if not results:
        return (f"No sold listings found for '{query}'. "
                f"Tip: Use web_search or search_and_read from the web-reader MCP for broader results.")
    if results and "error" in results[0]:
        return f"Error: {results[0]['error']}\n\nTip: Use mcp__web-reader__web_search to search for pricing data instead."

    prices = [r["price"] for r in results if r.get("price") is not None]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    lines = [
        f"eBay SOLD listings for '{query}' ({marketplace}):",
        f"Results: {len(results)} | Avg: ${avg_price:.2f} | Min: ${min_price:.2f} | Max: ${max_price:.2f}\n",
    ]

    for i, r in enumerate(results[:15], 1):
        price = f"${r['price']:.2f}" if r.get("price") else "N/A"
        lines.append(
            f"{i}. {r['title']}\n"
            f"   Sold: {price} {r.get('currency', 'AUD')} | {r.get('shipping', '')} | {r.get('condition', '')}\n"
            f"   {r.get('sold_info', '')}\n"
            f"   {r.get('url', '')}"
        )

    return "\n\n".join(lines)


def search_ebay_active(query: str, marketplace: str = "ebay.com.au") -> str:
    """Search eBay active listings to see current competitor ASKING prices.

    Use this to check what competitors are currently listing items for.
    Compare with sold prices to gauge actual vs aspirational pricing.
    Returns AUD prices from ebay.com.au by default.

    NOTE: eBay blocks automated scraping. For best results in Connected mode,
    also use mcp__web-reader__read_url or mcp__web-reader__web_search directly.
    """
    results = _search_active(query, marketplace)
    if not results:
        return (f"No active listings found for '{query}'. "
                f"Tip: Use web_search or search_and_read from the web-reader MCP for broader results.")
    if results and "error" in results[0]:
        return f"Error: {results[0]['error']}\n\nTip: Use mcp__web-reader__web_search to search for pricing data instead."

    prices = [r["price"] for r in results if r.get("price") is not None]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    lines = [
        f"eBay ACTIVE listings for '{query}' ({marketplace}):",
        f"Results: {len(results)} | Avg: ${avg_price:.2f} | Min: ${min_price:.2f} | Max: ${max_price:.2f}\n",
    ]

    for i, r in enumerate(results[:15], 1):
        price = f"${r['price']:.2f}" if r.get("price") else "N/A"
        lines.append(
            f"{i}. {r['title']}\n"
            f"   Asking: {price} {r.get('currency', 'AUD')} | {r.get('shipping', '')} | {r.get('condition', '')}\n"
            f"   {r.get('sold_info', '')}\n"
            f"   {r.get('url', '')}"
        )

    return "\n\n".join(lines)
