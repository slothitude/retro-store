from __future__ import annotations
import logging
import time
from flask import Flask, render_template, jsonify, request, g
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import init_db, migrate_db, seed_products, seed_kb, seed_batches
import config

csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("retromonkey")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.SECRET_KEY

    # Session security
    app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    if config.SESSION_COOKIE_SECURE:
        app.config["SESSION_COOKIE_SECURE"] = True

    # CSRF protection
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    csrf.init_app(app)

    # Rate limiting
    limiter.init_app(app)

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' js.stripe.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-src js.stripe.com; "
            "connect-src 'self' api.stripe.com"
        )
        return response

    # Request timing + logging
    @app.before_request
    def before_request():
        g.start_time = time.time()

    @app.after_request
    def log_request(response):
        if request.path.startswith(("/static", "/favicon")):
            return response
        duration = time.time() - g.get("start_time", time.time())
        log.info("%s %s %s %.0fms", request.method, request.path, response.status_code, duration * 1000)
        return response

    # Exempt Stripe webhook from CSRF (it sends JSON, not form data)
    csrf.exempt("routes.store.stripe_webhook")
    csrf.exempt("routes.store.health_check")

    # Make config available in all templates
    @app.context_processor
    def inject_config():
        return {"config": config}

    init_db()
    migrate_db()
    seed_products()
    seed_kb()
    seed_batches()

    # Register blueprints
    from routes.store import store_bp
    from routes.kb import kb_bp
    from routes.tickets import tickets_bp
    from routes.admin import admin_bp
    from routes.chat import chat_bp
    from routes.customers import customers_bp

    app.register_blueprint(store_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(customers_bp)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        log.exception("Internal server error: %s", request.path)
        return render_template("500.html"), 500

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return render_template("429.html"), 429

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5555, debug=True)
