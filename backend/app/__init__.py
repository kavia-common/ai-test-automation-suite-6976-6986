from flask import Flask
from flask_cors import CORS
from flask_smorest import Api

from .routes.health import blp as health_blp
from .routes.test_cases import blp as test_cases_blp
from .routes.ai import blp as ai_blp
from .storage.datastore import get_datastore

app = Flask(__name__)
app.url_map.strict_slashes = False

# Enable CORS for all origins (adjust as needed based on env vars)
CORS(app, resources={r"/*": {"origins": "*"}})

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

# Initialize datastore singleton at startup so it's ready for dependency usage
# This ensures backend/data directory is created and JSON files are loaded.
get_datastore()
