import os
from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

from .routes.health import blp as health_blp
from .routes.test_cases import blp as test_cases_blp
from .routes.ai import blp as ai_blp
from .routes.test_runs import blp as test_runs_blp
from .storage.datastore import get_datastore
from .services.runner import get_runner
from .realtime import init_app_for_realtime, register_ws_routes, sock  # WebSocket/SSE integration

app = Flask(__name__)
app.url_map.strict_slashes = False

# Determine allowed CORS origin:
# Prefer REACT_APP_FRONTEND_URL if provided (e.g., https://frontend.example.com or http://localhost:3000)
frontend_origin = os.getenv("REACT_APP_FRONTEND_URL", "").strip() or "http://localhost:3000"

# Enable CORS for the chosen origin; allow credentials if needed in the future
CORS(
    app,
    resources={r"/*": {"origins": [frontend_origin]}},
    supports_credentials=True,
)

# OpenAPI/Swagger configuration
app.config["API_TITLE"] = "My Flask API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Initialize API and register blueprints
api = Api(app)
api.register_blueprint(health_blp)
api.register_blueprint(test_cases_blp)
api.register_blueprint(ai_blp)
api.register_blueprint(test_runs_blp)

# Initialize datastore singleton at startup so it's ready for dependency usage
# This ensures backend/data directory is created and JSON files are loaded.
get_datastore()

# Initialize realtime (WS/SSE) and register routes
init_app_for_realtime(app)
if sock is not None:
    register_ws_routes(sock)

# Configure runner broadcaster to use realtime hub
runner = get_runner()
runner.set_broadcaster(app.config["RUNNER_BROADCASTER"])

# Enrich health metadata in app.config so the health route can report them
app.config["PORT"] = 3001  # This must align with run.py
app.config["WS_AVAILABLE"] = bool(sock is not None)
app.config["ALLOWED_ORIGIN"] = frontend_origin
