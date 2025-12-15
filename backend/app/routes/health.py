from flask import current_app
from flask_smorest import Blueprint
from flask.views import MethodView

# Note: Keep existing endpoint and path intact; just tidy tag/name text
blp = Blueprint("Health", "health", url_prefix="/", description="Health check route")

@blp.route("/")
class HealthCheck(MethodView):
    def get(self):
        """
        Health check endpoint: returns basic service status along with
        configuration details (port, ws availability, allowed CORS origin).
        """
        cfg = getattr(current_app, "config", {}) or {}
        return {
            "message": "Healthy",
            "port": cfg.get("PORT"),
            "ws_available": cfg.get("WS_AVAILABLE", False),
            "allowed_origin": cfg.get("ALLOWED_ORIGIN"),
        }
