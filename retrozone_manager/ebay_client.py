"""eBay REST API client — OAuth token refresh, inventory, offers, orders.

Uses httpx (already a dependency). Credentials from config.py env vars:
  EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REFRESH_TOKEN

Marketplace: EBAY_AU (ebay.com.au)
"""
import os
import time
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import httpx
import config as flask_config

# eBay API endpoints
EBAY_API_BASE = "https://api.ebay.com"
EBAY_AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"

# eBay AU marketplace ID
EBAY_AU = "EBAY_AU"


class EbayClient:
    """eBay Sell API client with automatic OAuth token refresh."""

    def __init__(self, client_id=None, client_secret=None, refresh_token=None):
        self.client_id = client_id or flask_config.EBAY_CLIENT_ID
        self.client_secret = client_secret or flask_config.EBAY_CLIENT_SECRET
        self.refresh_token = refresh_token or flask_config.EBAY_REFRESH_TOKEN

        self._access_token = None
        self._token_expires_at = 0
        self._client = httpx.Client(timeout=30.0)

    def _ensure_token(self):
        """Refresh OAuth token if expired (tokens last ~2h)."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return

        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise RuntimeError(
                "eBay credentials not configured. Set EBAY_CLIENT_ID, "
                "EBAY_CLIENT_SECRET, EBAY_REFRESH_TOKEN in .env"
            )

        resp = self._client.post(
            EBAY_AUTH_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "scope": (
                    "https://api.ebay.com/oauth/api_scope/sell.inventory "
                    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly "
                    "https://api.ebay.com/oauth/api_scope/sell.marketing "
                    "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly "
                    "https://api.ebay.com/oauth/api_scope/sell.account "
                    "https://api.ebay.com/oauth/api_scope/sell.account.readonly "
                    "https://api.ebay.com/oauth/api_scope/sell.fulfillment "
                    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly"
                ),
            },
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)

    def _headers(self):
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Content-Language": "en-AU",
        }

    # ── Inventory API ──

    def create_or_replace_inventory_item(self, sku: str, product_data: dict):
        """Create or replace an inventory item.

        product_data keys: title, description, condition, category, image_urls,
                          item_specifics (dict), quantity, price_cents
        """
        payload = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": product_data.get("quantity", 1)
                }
            },
            "condition": product_data.get("condition", "NEW"),
            "product": {
                "title": product_data["title"],
                "description": product_data.get("description", ""),
                "aspects": product_data.get("item_specifics", {}),
                "imageUrls": product_data.get("image_urls", []),
            },
        }

        resp = self._client.put(
            f"{EBAY_API_BASE}/sell/inventory/v1/inventory_item/{sku}",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        return {"status": resp.status_code, "sku": sku}

    def get_inventory_item(self, sku: str):
        """Get inventory item details."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/inventory/v1/inventory_item/{sku}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Offer API ──

    def create_offer(self, sku: str, listing_data: dict):
        """Create a listing offer for an inventory item.

        listing_data keys: price_cents, category_id, listing_policy_id,
                          merchant_location_key, marketplace_id
        """
        marketplace = listing_data.get("marketplace_id", EBAY_AU)
        payload = {
            "sku": sku,
            "marketplaceId": marketplace,
            "format": "FIXED_PRICE",
            "listingDescription": listing_data.get("description", ""),
            "availableQuantity": listing_data.get("quantity", 1),
            "categoryId": listing_data.get("category_id", "139971"),
            "listingPolicies": {
                "paymentPolicyId": listing_data.get("payment_policy_id", ""),
                "returnPolicyId": listing_data.get("return_policy_id", ""),
                "fulfillmentPolicyId": listing_data.get("fulfillment_policy_id", ""),
            },
            "pricingSummary": {
                "price": {
                    "value": f"{listing_data['price_cents'] / 100:.2f}",
                    "currency": "AUD",
                }
            },
            "merchantLocationKey": listing_data.get("merchant_location_key", ""),
        }

        resp = self._client.post(
            f"{EBAY_API_BASE}/sell/inventory/v1/offer",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def publish_offer(self, offer_id: str):
        """Publish an offer — makes the listing go live."""
        resp = self._client.post(
            f"{EBAY_API_BASE}/sell/inventory/v1/offer/{offer_id}/publish",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_offer(self, offer_id: str):
        """Get offer details."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/inventory/v1/offer/{offer_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def update_offer_quantity(self, offer_id: str, qty: int):
        """Update available quantity on an existing offer."""
        # Get current offer, update quantity
        offer = self.get_offer(offer_id)
        offer["availableQuantity"] = qty

        resp = self._client.put(
            f"{EBAY_API_BASE}/sell/inventory/v1/offer/{offer_id}",
            headers=self._headers(),
            json=offer,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Fulfillment API (Orders) ──

    def get_orders(self, filter_str: str = None, limit: int = 50, offset: int = 0):
        """Get orders from eBay. filter_str examples:
          'orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}'
          'creationdate:[2026-01-01T00:00:00.000Z..]'
        """
        params = {"limit": limit, "offset": offset}
        if filter_str:
            params["filter"] = filter_str

        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/fulfillment/v1/order",
            headers=self._headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def get_order(self, order_id: str):
        """Get a single order by ID."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/fulfillment/v1/order/{order_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Account API (Policies) ──

    def get_fulfillment_policies(self, marketplace_id: str = EBAY_AU):
        """Get shipping/fulfillment policies."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/account/v1/fulfillment_policy",
            headers=self._headers(),
            params={"marketplace_id": marketplace_id},
        )
        resp.raise_for_status()
        return resp.json()

    def get_payment_policies(self, marketplace_id: str = EBAY_AU):
        """Get payment policies."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/account/v1/payment_policy",
            headers=self._headers(),
            params={"marketplace_id": marketplace_id},
        )
        resp.raise_for_status()
        return resp.json()

    def get_return_policies(self, marketplace_id: str = EBAY_AU):
        """Get return policies."""
        resp = self._client.get(
            f"{EBAY_API_BASE}/sell/account/v1/return_policy",
            headers=self._headers(),
            params={"marketplace_id": marketplace_id},
        )
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()
