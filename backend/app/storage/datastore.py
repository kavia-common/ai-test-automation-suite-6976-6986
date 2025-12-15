from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional

from app.models.test_case import TestCase
from app.models.test_run import TestRun


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
TEST_CASES_FILE = os.path.join(DATA_DIR, "test_cases.json")
TEST_RUNS_FILE = os.path.join(DATA_DIR, "test_runs.json")


class _Singleton(type):
    """Metaclass to implement the Singleton pattern in a thread-safe way."""
    _instances: Dict[type, "Datastore"] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with _Singleton._lock:
            if cls not in _Singleton._instances:
                _Singleton._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return _Singleton._instances[cls]


class Datastore(metaclass=_Singleton):
    """
    Thread-safe in-memory datastore with JSON file persistence.

    This store provides CRUD operations for TestCase and TestRun entities.
    Data is kept in memory and periodically flushed to disk on each write
    operation, to simple JSON files under backend/data/.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._test_cases: Dict[str, TestCase] = {}
        self._test_runs: Dict[str, TestRun] = {}
        # Ensure data directory exists and load from disk if available
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_from_disk()

    # ------------- Internal persistence helpers -------------

    def _load_from_disk(self) -> None:
        """Load persisted data into memory."""
        with self._lock:
            # Load test cases
            if os.path.exists(TEST_CASES_FILE):
                try:
                    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                        self._test_cases = {tc["id"]: TestCase.from_dict(tc) for tc in raw or []}
                except Exception:
                    # Best-effort; start with empty on failure
                    self._test_cases = {}
            # Load test runs
            if os.path.exists(TEST_RUNS_FILE):
                try:
                    with open(TEST_RUNS_FILE, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                        self._test_runs = {tr["id"]: TestRun.from_dict(tr) for tr in raw or []}
                except Exception:
                    self._test_runs = {}

    def _flush_test_cases(self) -> None:
        with open(TEST_CASES_FILE, "w", encoding="utf-8") as f:
            json.dump([tc.to_dict() for tc in self._test_cases.values()], f, indent=2)

    def _flush_test_runs(self) -> None:
        with open(TEST_RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump([tr.to_dict() for tr in self._test_runs.values()], f, indent=2)

    # ------------- PUBLIC: TestCase operations -------------

    # PUBLIC_INTERFACE
    def list_test_cases(self) -> List[TestCase]:
        """Return a list of all TestCase objects."""
        with self._lock:
            return list(self._test_cases.values())

    # PUBLIC_INTERFACE
    def get_test_case(self, test_case_id: str) -> Optional[TestCase]:
        """Get a TestCase by id, or None if not found."""
        with self._lock:
            return self._test_cases.get(test_case_id)

    # PUBLIC_INTERFACE
    def create_test_case(self, data: dict) -> TestCase:
        """Create and persist a new TestCase from provided dictionary data."""
        with self._lock:
            tc = TestCase.from_dict(data or {})
            tc.validate()
            self._test_cases[tc.id] = tc
            self._flush_test_cases()
            return tc

    # PUBLIC_INTERFACE
    def update_test_case(self, test_case_id: str, updates: dict) -> Optional[TestCase]:
        """Update an existing TestCase; returns updated or None if not found."""
        with self._lock:
            tc = self._test_cases.get(test_case_id)
            if not tc:
                return None
            tc.update(updates or {})
            tc.validate()
            self._flush_test_cases()
            return tc

    # PUBLIC_INTERFACE
    def delete_test_case(self, test_case_id: str) -> bool:
        """Delete a TestCase by id. Returns True if deleted, False if not found."""
        with self._lock:
            existed = test_case_id in self._test_cases
            if existed:
                del self._test_cases[test_case_id]
                self._flush_test_cases()
            return existed

    # ------------- PUBLIC: TestRun operations -------------

    # PUBLIC_INTERFACE
    def list_test_runs(self) -> List[TestRun]:
        """Return a list of all TestRun objects."""
        with self._lock:
            return list(self._test_runs.values())

    # PUBLIC_INTERFACE
    def get_test_run(self, test_run_id: str) -> Optional[TestRun]:
        """Get a TestRun by id, or None if not found."""
        with self._lock:
            return self._test_runs.get(test_run_id)

    # PUBLIC_INTERFACE
    def create_test_run(self, data: dict) -> TestRun:
        """Create and persist a new TestRun from provided dictionary data."""
        with self._lock:
            tr = TestRun.from_dict(data or {})
            tr.validate()
            self._test_runs[tr.id] = tr
            self._flush_test_runs()
            return tr

    # PUBLIC_INTERFACE
    def update_test_run(self, test_run_id: str, updates: dict) -> Optional[TestRun]:
        """Update an existing TestRun; returns updated or None if not found."""
        with self._lock:
            tr = self._test_runs.get(test_run_id)
            if not tr:
                return None
            # Apply known updates
            if "status" in updates:
                tr.set_status(updates["status"])
            if "logs" in updates and isinstance(updates["logs"], list):
                # extend logs
                for entry in updates["logs"]:
                    tr.append_log(entry)
            if "results" in updates and isinstance(updates["results"], dict):
                tr.update_results(updates["results"])
            if "metadata" in updates and isinstance(updates["metadata"], dict):
                tr.metadata.update(updates["metadata"])
                tr.updated_at = tr.updated_at  # no-op to reflect change
            tr.validate()
            self._flush_test_runs()
            return tr

    # PUBLIC_INTERFACE
    def delete_test_run(self, test_run_id: str) -> bool:
        """Delete a TestRun by id. Returns True if deleted, False if not found."""
        with self._lock:
            existed = test_run_id in self._test_runs
            if existed:
                del self._test_runs[test_run_id]
                self._flush_test_runs()
            return existed


# PUBLIC_INTERFACE
def get_datastore() -> Datastore:
    """Return the singleton Datastore instance."""
    return Datastore()
