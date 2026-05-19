"""RetroZone MCP Server — FastMCP stdio entry point for external tools."""
import sys
import os

# Ensure retro_store root is on sys.path for config/db imports
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastmcp import FastMCP

mcp = FastMCP("retro-tools")

# Import and register all tools
from .tools.product_search import search_alibaba, get_alibaba_product_details, search_aliexpress
from .tools.competitor_pricing import search_ebay_sold, search_ebay_active
from .tools.email_tools import check_inbox, get_email, search_emails, draft_email
from .tools.supplier_tracker import (
    add_supplier, list_suppliers, log_supplier_order,
    get_supplier_orders,
)
from .tools.ebay_pricing import calculate_ebay_price, compare_channel_pricing
from .tools.ebay_listing_tools import (
    list_ebay_listings, get_ebay_listing, create_ebay_listing_draft,
    sync_ebay_orders,
)

# Register product search tools
mcp.tool(search_alibaba)
mcp.tool(get_alibaba_product_details)
mcp.tool(search_aliexpress)

# Register competitor pricing tools
mcp.tool(search_ebay_sold)
mcp.tool(search_ebay_active)

# Register email tools
mcp.tool(check_inbox)
mcp.tool(get_email)
mcp.tool(search_emails)
mcp.tool(draft_email)

# Register supplier tracker tools
mcp.tool(add_supplier)
mcp.tool(list_suppliers)
mcp.tool(log_supplier_order)
mcp.tool(get_supplier_orders)

# Register eBay pricing tools
mcp.tool(calculate_ebay_price)
mcp.tool(compare_channel_pricing)

# Register eBay listing tools
mcp.tool(list_ebay_listings)
mcp.tool(get_ebay_listing)
mcp.tool(create_ebay_listing_draft)
mcp.tool(sync_ebay_orders)

if __name__ == "__main__":
    mcp.run(transport="stdio")
