import os
from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)

    # The static frontend is hosted separately (Vercel) and calls this API cross-origin, so
    # restrict CORS to the configured origin(s) for /api/*. ALLOWED_ORIGINS is a comma-separated
    # list (e.g. "https://atm-wigs.vercel.app"); defaults to "*" for local/dev.
    origins_env = os.getenv("ALLOWED_ORIGINS", "*").strip()
    origins = [o.strip() for o in origins_env.split(",") if o.strip()] or ["*"]
    CORS(app, resources={r"/api/*": {"origins": origins}})

    from app.routes import register_routes
    register_routes(app)

    return app
