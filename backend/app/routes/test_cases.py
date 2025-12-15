from __future__ import annotations

from flask_smorest import Blueprint, abort
from flask.views import MethodView
from marshmallow import Schema, fields, EXCLUDE
from typing import Any, Dict

from app.storage.datastore import get_datastore

# Define Blueprint for Test Cases
blp = Blueprint(
    "Test Cases",
    "test-cases",
    url_prefix="/api/test-cases",
    description="CRUD operations for Test Cases",
)


# Marshmallow Schemas for request/response validation
class TestCaseMetadataSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    # Arbitrary metadata as key-value
    # Using Dict for flexible metadata; values are untyped Any via additionalProperties
    # Marshmallow will accept dict here.
    # We don't strictly validate internal structure.
    # No fields needed explicitly; allow dicts.


class TestCaseBaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    title = fields.String(required=True, description="Short, human-readable name for the test case")
    description = fields.String(required=False, allow_none=True, load_default="", description="Detailed description")
    steps = fields.List(fields.Raw(), load_default=list, description="List of steps for the test case")
    tags = fields.List(fields.String(), load_default=list, description="Labels for organization")
    metadata = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict, description="Arbitrary metadata")


class TestCaseCreateSchema(TestCaseBaseSchema):
    """Schema for creating a TestCase."""
    pass


class TestCaseUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    title = fields.String(description="Updated title")
    description = fields.String(allow_none=True, description="Updated description")
    steps = fields.List(fields.Raw(), description="Updated steps")
    tags = fields.List(fields.String(), description="Updated tags")
    metadata = fields.Dict(keys=fields.String(), values=fields.Raw(), description="Updated metadata")


class TestCaseSchema(TestCaseBaseSchema):
    id = fields.String(required=True, description="Unique ID of the test case (UUID)")
    created_at = fields.String(required=True, description="Creation timestamp (ISO8601, UTC)")
    updated_at = fields.String(required=True, description="Update timestamp (ISO8601, UTC)")


@blp.route("/")
class TestCaseListResource(MethodView):
    @blp.response(200, TestCaseSchema(many=True), description="List all test cases")
    @blp.doc(summary="List Test Cases", description="Retrieve a list of all available test cases.")
    def get(self):
        """
        List all Test Cases.
        Returns a JSON array of TestCase objects.
        """
        ds = get_datastore()
        data = [tc.to_dict() for tc in ds.list_test_cases()]
        return data

    @blp.arguments(TestCaseCreateSchema, location="json")
    @blp.response(201, TestCaseSchema, description="Created test case")
    @blp.doc(summary="Create Test Case", description="Create a new test case record from the provided payload.")
    def post(self, json_data: Dict[str, Any]):
        """
        Create a Test Case.
        Body: TestCaseCreateSchema
        Returns the created TestCase.
        """
        ds = get_datastore()
        try:
            tc = ds.create_test_case(json_data or {})
        except ValueError as e:
            abort(400, message=str(e))
        return tc.to_dict()


@blp.route("/<string:test_case_id>")
class TestCaseResource(MethodView):
    @blp.response(200, TestCaseSchema, description="Fetched test case by ID")
    @blp.doc(
        summary="Get Test Case by ID",
        description="Retrieve a single test case by its unique identifier.",
        parameters=[{"in": "path", "name": "test_case_id", "schema": {"type": "string"}, "required": True}],
    )
    def get(self, test_case_id: str):
        """
        Get a Test Case by ID.
        Path: test_case_id
        """
        ds = get_datastore()
        tc = ds.get_test_case(test_case_id)
        if not tc:
            abort(404, message="TestCase not found")
        return tc.to_dict()

    @blp.arguments(TestCaseUpdateSchema, location="json")
    @blp.response(200, TestCaseSchema, description="Updated test case")
    @blp.doc(
        summary="Update Test Case",
        description="Update an existing test case by ID with provided fields.",
        parameters=[{"in": "path", "name": "test_case_id", "schema": {"type": "string"}, "required": True}],
    )
    def put(self, json_data: Dict[str, Any], test_case_id: str):
        """
        Update a Test Case by ID.
        Path: test_case_id
        Body: TestCaseUpdateSchema (partial fields allowed)
        """
        ds = get_datastore()
        updated = ds.update_test_case(test_case_id, json_data or {})
        if not updated:
            abort(404, message="TestCase not found")
        return updated.to_dict()

    @blp.response(204, description="Deleted")
    @blp.doc(
        summary="Delete Test Case",
        description="Delete an existing test case by its ID.",
        parameters=[{"in": "path", "name": "test_case_id", "schema": {"type": "string"}, "required": True}],
    )
    def delete(self, test_case_id: str):
        """
        Delete a Test Case by ID.
        Returns 204 on successful deletion, 404 if not found.
        """
        ds = get_datastore()
        deleted = ds.delete_test_case(test_case_id)
        if not deleted:
            abort(404, message="TestCase not found")
        return "", 204
