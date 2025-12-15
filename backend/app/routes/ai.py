from __future__ import annotations

from typing import Any, Dict

from flask_smorest import Blueprint, abort
from flask.views import MethodView
from marshmallow import Schema, fields, EXCLUDE, validates_schema, ValidationError

from app.services.ai_authoring import generate_suggested_steps


# Blueprint for AI authoring
blp = Blueprint(
    "AI Authoring",
    "ai",
    url_prefix="/api/ai",
    description="AI-powered authoring utilities",
)


# Request schema
class AuthorRequestSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    prompt = fields.String(
        required=True,
        description="User input describing the test intent",
    )
    context = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        load_default=dict,
        description="Optional contextual information to guide the authoring",
    )

    @validates_schema
    def _validate_content(self, data: Dict[str, Any], **kwargs) -> None:
        # Ensure prompt is not empty/whitespace
        prompt = data.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationError("prompt must be a non-empty string", field_name="prompt")


# Response schema
class AuthorResponseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    suggested_steps = fields.List(
        fields.Dict(keys=fields.String(), values=fields.Raw()),
        required=True,
        description="Structured step suggestions",
    )
    rationale = fields.String(
        required=True,
        description="Explanation of the suggestion process",
    )


@blp.route("/author")
class AIAuthorResource(MethodView):
    @blp.arguments(AuthorRequestSchema, location="json")
    @blp.response(200, AuthorResponseSchema, description="AI-suggested steps and rationale")
    @blp.doc(
        summary="Generate suggested test steps",
        description=(
            "Generate deterministic AI-like suggestions for test steps based on a prompt and optional context. "
            "This implementation uses an offline heuristic (no external API calls) to provide stable suggestions."
        ),
    )
    def post(self, json_data: Dict[str, Any]):
        """
        AI Authoring endpoint.

        Request body:
        - prompt: string (required) - description of the test intent
        - context: object (optional) - arbitrary contextual information

        Returns:
        - 200 OK with { suggested_steps: list[dict], rationale: str }
        - 400/422 for validation or processing errors
        """
        try:
            prompt: str = json_data.get("prompt", "")
            context: Dict[str, Any] = json_data.get("context", {}) or {}
            result = generate_suggested_steps(prompt=prompt, context=context)
            # Basic shape validation before returning
            if not isinstance(result, dict) or "suggested_steps" not in result or "rationale" not in result:
                abort(500, message="AI authoring service returned an unexpected result shape")
            return result
        except ValidationError as ve:
            # Marshmallow schema validation error surfaced explicitly
            abort(422, message=str(ve))
        except ValueError as ve:
            abort(400, message=str(ve))
        except Exception as e:
            # Generic server error
            abort(500, message=f"Failed to generate suggested steps: {e}")
