from flask_smorest import Blueprint
from flask.views import MethodView

# Note: Keep existing endpoint and path intact; just tidy tag/name text
blp = Blueprint("Health", "health", url_prefix="/", description="Health check route")

@blp.route("/")
class HealthCheck(MethodView):
    def get(self):
        """Health check endpoint: returns basic service status."""
        return {"message": "Healthy"}
