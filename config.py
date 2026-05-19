import os
from dotenv import load_dotenv

load_dotenv()

# Stripe
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# App
SITE_URL = os.getenv("SITE_URL", "https://retromonkey.ddns.net")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_ENV = os.getenv("FLASK_ENV", "development")
DATABASE = os.path.join(os.path.dirname(__file__), "retro_store.db")
KB_DIR = os.path.join(os.path.dirname(__file__), "kb")

# Store info
STORE_NAME = "RetroMonkey"
STORE_TAGLINE = "Retro Gaming Handhelds & Accessories"
CURRENCY = "aud"

# Business (required for Australian compliance)
ABN = os.getenv("ABN", "")  # e.g. "12 345 678 901"
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "RetroMonkey")
GST_RATE = 0.10  # 10% GST

# Session security
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Email (Zoho Mail — free custom domain)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.zoho.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "orders@retromonkey.com.au")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "orders@retromonkey.com.au")

# eBay (for multi-channel selling)
EBAY_CLIENT_ID = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN", "")
EBAY_AU_MARKETPLACE_ID = os.getenv("EBAY_AU_MARKETPLACE_ID", "EBAY_AU")

# Backups
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(__file__), "backups"))
