import os
from dotenv import load_dotenv

load_dotenv()

# Stripe
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# App
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
FLASK_ENV = os.getenv("FLASK_ENV", "development")
DATABASE = os.path.join(os.path.dirname(__file__), "retro_store.db")
KB_DIR = os.path.join(os.path.dirname(__file__), "kb")

# Store info
STORE_NAME = "RetroZone"
STORE_TAGLINE = "Retro Gaming Handhelds & Accessories"
CURRENCY = "aud"
