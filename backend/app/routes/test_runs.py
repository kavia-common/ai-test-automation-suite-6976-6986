from __future__ import annotations

from typing import Any, Dict

from flask_smorest import Blueprint, abort
from flask.views import MethodView
from marshmallow import Schema, fields, EXCLUDE

from app.storage.datastore import get_datastore
from app.services.runner import get_runner

# Blueprint for Test Runs
blp = Blueprint(
    "Test Runs",
    "test-runs",
    url_prefix="/api/test-runs",
    description="Create and query Test Runs and their logs",
)


# Schemas
class TestRunBaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    test_case_id = fields.String(
        required=False,
        allow_none=True,
        description="Optional TestCase ID associated with this run",
    )
    metadata = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        load_default=dict,
        description="Arbitrary metadata for the run (e.g., environment, runner hints)",
    )


class TestRunCreateSchema(TestRunBaseSchema):
    pass


class TestRunSchema(TestRunBaseSchema):
    id = fields.String(required=True, description="Run ID (UUID)")
    status = fields.String(required=True, description="Execution status")
    started_at = fields.String(allow_none=True, description="Start timestamp (ISO8601, UTC)")
    finished_at = fields.String(allow_none=True, description="Finish timestamp (ISO8601, UTC)")
    logs = fields.List(fields.Raw(), required=True, description="Log entries")
    results = fields.Dict(keys=fields.String(), values=fields.Raw(), required=True, description="Result data")
    created_at = fields.String(required=True, description="Creation timestamp (ISO8601, UTC)")
    updated_at = fields.String(required=True, description="Update timestamp (ISO8601, UTC)")


class LogsQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    offset = fields.Integer(load_default=0, description="Start index for logs (0-based)")
    limit = fields.Integer(load_default=0, description="Max number of logs to return; 0 returns all")
    full = fields.Boolean(load_default=False, description="If true, ignore pagination and return full logs")


class LogsResponseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    logs = fields.List(fields.Raw(), required=True, description="Log entries")
    total = fields.Integer(required=True, description="Total number of logs available")
    offset = fields.Integer(required=True, description="Offset used for this response")
    limit = fields.Integer(required=True, description="Limit used for this response")


@blp.route("/")
class TestRunListResource(MethodView):
    @blp.response(200, TestRunSchema(many=True), description="List all test runs")
    @blp.doc(summary="List Test Runs", description="Retrieve all test runs.")
    def get(self):
        """
        List all Test Runs.
        Returns a JSON array of TestRun objects.
        """
        ds = get_datastore()
        data = [tr.to_dict() for tr in ds.list_test_runs()]
        return data

    @blp.arguments(TestRunCreateSchema, location="json")
    @blp.response(201, TestRunSchema, description="Created and enqueued test run")
    @blp.doc(
        summary="Create and Enqueue a Test Run",
        description="Create a new TestRun record and enqueue it for simulated execution.",
    )
    def post(self, json_data: Dict[str, Any]):
        """
        Create and enqueue a Test Run.

        Body: TestRunCreateSchema
        Returns the created TestRun (status initially queued), and starts execution in background.
        """
        ds = get_datastore()
        tr = ds.create_test_run(json_data or {})
        # enqueue the run
        get_runner().enqueue(tr)
        return tr.to_dict()


@blp.route("/<string:test_run_id>")
class TestRunResource(MethodView):
    @blp.response(200, TestRunSchema, description="Fetched test run by ID")
    @blp.doc(
        summary="Get Test Run by ID",
        description="Retrieve a single test run by its ID.",
        parameters=[{"in": "path", "name": "test_run_id", "schema": {"type": "string"}, "required": True}],
    )
    def get(self, test_run_id: str):
        """
        Get a Test Run by ID.
        Path: test_run_id
        """
        ds = get_datastore()
        tr = ds.get_test_run(test_run_id)
        if not tr:
            abort(404, message="TestRun not found")
        return tr.to_dict()


@blp.route("/<string:test_run_id>/logs")
class TestRunLogsResource(MethodView):
    @blp.arguments(LogsQuerySchema, location="query")
    @blp.response(200, LogsResponseSchema, description="Logs for a test run")
    @blp.doc(
        summary="Get Test Run Logs",
        description="Retrieve logs for the test run. Supports pagination via offset/limit or full retrieval via ?full=true.",
        parameters=[
            {"in": "path", "name": "test_run_id", "schema": {"type": "string"}, "required": True},
            {"in": "query", "name": "offset", "schema": {"type": "integer"}},
            {"in": "query", "name": "limit", "schema": {"type": "integer"}},
            {"in": "query", "name": "full", "schema": {"type": "boolean"}},
        ],
    )
    def get(self, query_args: Dict[str, Any], test_run_id: str):
        """
        Get logs for a Test Run.

        Query parameters:
        - offset (int): start index; default 0
        - limit (int): max number of logs; 0 or missing means all
        - full (bool): if true, return full logs ignoring pagination

        Returns:
        - logs: list
        - total: int
        - offset: int
        - limit: int
        """
        ds = get_datastore()
        tr = ds.get_test_run(test_run_id)
        if not tr:
            abort(404, message="TestRun not found")
        logs = tr.logs or []
        total = len(logs)

        full = bool(query_args.get("full", False))
        if full:
            return {"logs": logs, "total": total, "offset": 0, "limit": total}

        offset = int(query_args.get("offset", 0) or 0)
        limit = int(query_args.get("limit", 0) or 0)

        if offset < 0:
            offset = 0
        if limit < 0:
            limit = 0

        if limit == 0:
            sliced = logs[offset:]
            used_limit = total - offset if offset < total else 0
        else:
            sliced = logs[offset: offset + limit]
            used_limit = limit

        return {"logs": sliced, "total": total, "offset": offset, "limit": used_limit}
