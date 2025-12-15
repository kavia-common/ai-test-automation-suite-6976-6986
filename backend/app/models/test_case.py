from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List


def _now_iso() -> str:
    """Return current UTC time in ISO format with 'Z'."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class TestCase:
    """
    Represents a test case authored by the user or AI.

    Fields:
    - id: Unique identifier (UUID string).
    - title: Short, human-readable name for the test case.
    - description: Detailed description or intent of the test.
    - steps: List of step descriptions or structured step data.
    - created_at: ISO8601 string when the test case was created (UTC).
    - updated_at: ISO8601 string when the test case was last updated (UTC).
    - tags: Optional labels for organization/filtering.
    - metadata: Arbitrary extra information (e.g., AI prompts, authorship).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    steps: List[Any] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # PUBLIC_INTERFACE
    def to_dict(self) -> Dict[str, Any]:
        """Serialize TestCase to a JSON-serializable dictionary."""
        return asdict(self)

    # PUBLIC_INTERFACE
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TestCase":
        """Deserialize a TestCase from a dictionary, with sensible defaults."""
        return TestCase(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            steps=list(data.get("steps", [])),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )

    # PUBLIC_INTERFACE
    def update(self, updates: Dict[str, Any]) -> None:
        """Apply partial updates and refresh updated_at."""
        for key in ("title", "description", "steps", "tags", "metadata"):
            if key in updates:
                setattr(self, key, updates[key])
        # Always refresh updated_at on update
        self.updated_at = _now_iso()

    # PUBLIC_INTERFACE
    def validate(self) -> None:
        """Validate essential fields, raising ValueError on invalid data."""
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title is required and must be a non-empty string")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.steps, list):
            raise ValueError("steps must be a list")
        if not isinstance(self.tags, list):
            raise ValueError("tags must be a list of strings")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be an object/dict")
        # Optional: further checks (lengths, step structure, etc.)

