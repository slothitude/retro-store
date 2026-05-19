from __future__ import annotations
from flask import Flask
from db import init_db, seed_products, seed_kb, seed_batches
import config


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.SECRET_KEY

    init_db()
    seed_products()
    seed_kb()
    seed_batches()

    # Register blueprints
    from routes.store import store_bp
    from routes.kb import kb_bp
    from routes.tickets import tickets_bp
    from routes.admin import admin_bp
    from routes.chat import chat_bp

    app.register_blueprint(store_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5555, debug=True)
