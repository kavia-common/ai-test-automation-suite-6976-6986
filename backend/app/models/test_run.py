from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    """Return current UTC time in ISO format with 'Z'."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


VALID_STATUSES = {"queued", "running", "passed", "failed", "error", "canceled"}


@dataclass
class TestRun:
    """
    Represents execution of one or more test cases.

    Fields:
    - id: Unique identifier (UUID string).
    - test_case_id: The TestCase id this run belongs to (single-case run).
    - status: Execution status (queued, running, passed, failed, error, canceled).
    - started_at: ISO8601 when execution started (UTC).
    - finished_at: ISO8601 when execution finished (UTC) or None.
    - logs: Ordered list of log lines or structured entries.
    - results: Arbitrary result payload (assertions, metrics).
    - created_at: ISO8601 when the run record was created.
    - updated_at: ISO8601 when the run record was last updated.
    - metadata: Arbitrary extra information (e.g., environment, runner info).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    test_case_id: Optional[str] = None
    status: str = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    logs: List[Any] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # PUBLIC_INTERFACE
    def to_dict(self) -> Dict[str, Any]:
        """Serialize TestRun to a JSON-serializable dictionary."""
        return asdict(self)

    # PUBLIC_INTERFACE
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TestRun":
        """Deserialize a TestRun from a dictionary, with sensible defaults."""
        return TestRun(
            id=data.get("id", str(uuid.uuid4())),
            test_case_id=data.get("test_case_id"),
            status=data.get("status", "queued"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            logs=list(data.get("logs", [])),
            results=dict(data.get("results", {})),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            metadata=dict(data.get("metadata", {})),
        )

    # PUBLIC_INTERFACE
    def set_status(self, status: str) -> None:
        """Set run status and update timestamps accordingly."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        # Transition-based timestamp management
        if self.status in {"queued"} and status == "running" and not self.started_at:
            self.started_at = _now_iso()
        if status in {"passed", "failed", "error", "canceled"}:
            self.finished_at = _now_iso()
        self.status = status
        self.updated_at = _now_iso()

    # PUBLIC_INTERFACE
    def append_log(self, entry: Any) -> None:
        """Append a log entry and refresh updated_at."""
        self.logs.append(entry)
        self.updated_at = _now_iso()

    # PUBLIC_INTERFACE
    def update_results(self, results: Dict[str, Any]) -> None:
        """Merge in new result data and refresh updated_at."""
        self.results.update(results or {})
        self.updated_at = _now_iso()

    # PUBLIC_INTERFACE
    def validate(self) -> None:
        """Validate essential fields, raising ValueError on invalid data."""
        if self.status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        if self.test_case_id is not None and not isinstance(self.test_case_id, str):
            raise ValueError("test_case_id must be a string when provided")
        if not isinstance(self.logs, list):
            raise ValueError("logs must be a list")
        if not isinstance(self.results, dict):
            raise ValueError("results must be an object/dict")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be an object/dict")
