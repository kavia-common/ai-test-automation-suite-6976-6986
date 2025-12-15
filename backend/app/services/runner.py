from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from app.models.test_run import TestRun
from app.storage.datastore import get_datastore


@dataclass
class BroadcastEvent:
    """Simple broadcast event structure for future WS/SSE usage."""
    type: str
    payload: Dict[str, Any]


class SimulatedRunner:
    """
    Simulated test runner that executes test runs in background threads.

    Behavior:
    - Newly enqueued runs transition queued -> running -> passed/failed.
    - While running, append deterministic logs periodically.
    - Persist state/logs through the Datastore.
    - Exposes a no-op capable broadcaster hook for future WS/SSE.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_threads: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, threading.Event] = {}
        self._broadcaster: Optional[Callable[[BroadcastEvent], None]] = None

    # PUBLIC_INTERFACE
    def set_broadcaster(self, fn: Optional[Callable[[BroadcastEvent], None]]) -> None:
        """
        Set an optional broadcaster function to emit real-time events.

        The function should accept a BroadcastEvent; if None, broadcasting is disabled.
        """
        with self._lock:
            self._broadcaster = fn

    def _broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Internal helper to send a broadcast event if broadcaster is configured."""
        with self._lock:
            fn = self._broadcaster
        if fn is not None:
            try:
                fn(BroadcastEvent(type=event_type, payload=payload))
            except Exception:
                # Swallow broadcaster errors to avoid disrupting runner flow.
                pass

    # PUBLIC_INTERFACE
    def enqueue(self, run: TestRun) -> None:
        """
        Enqueue a TestRun for execution in a background thread.
        If a run with same id is already active, do nothing (idempotent enqueue).
        """
        with self._lock:
            if run.id in self._active_threads:
                return
            stop_event = threading.Event()
            self._stop_flags[run.id] = stop_event
            t = threading.Thread(target=self._execute, args=(run.id, stop_event), daemon=True)
            self._active_threads[run.id] = t
            t.start()

    def _finalize_thread(self, run_id: str) -> None:
        with self._lock:
            self._active_threads.pop(run_id, None)
            self._stop_flags.pop(run_id, None)

    def _execute(self, run_id: str, stop_event: threading.Event) -> None:
        """
        Simulated execution lifecycle:
        - set status running
        - append a few logs over time
        - randomly or deterministically decide pass/fail
        - set final status and results
        """
        ds = get_datastore()
        run = ds.get_test_run(run_id)
        if not run:
            # Nothing to do if not found
            self._finalize_thread(run_id)
            return

        # Move to running
        ds.update_test_run(run_id, {"status": "running"})
        self._broadcast("run_status", {"id": run_id, "status": "running"})

        try:
            # Produce deterministic pseudo-randomness based on UUID to keep consistent behavior.
            # Use the first hex char to decide number of steps and final outcome.
            try:
                seed_hex = (run.id or "").replace("-", "")
                seed_val = int(seed_hex[:2], 16) if seed_hex else 0
            except Exception:
                seed_val = 0

            steps = 5 + (seed_val % 4)  # 5..8 steps
            # Emit logs periodically
            for i in range(1, steps + 1):
                if stop_event.is_set():
                    ds.update_test_run(run_id, {
                        "status": "canceled",
                        "logs": [f"[{i}/{steps}] Canceled by user"],
                        "results": {"canceled_step": i},
                    })
                    self._broadcast("run_status", {"id": run_id, "status": "canceled"})
                    self._finalize_thread(run_id)
                    return

                # Append a log line
                log_line = f"[{i}/{steps}] Executing simulated step {i}"
                ds.update_test_run(run_id, {"logs": [log_line]})
                self._broadcast("run_log", {"id": run_id, "log": log_line})
                time.sleep(0.3)  # small delay to simulate work

            # Decide final result: even seed passes, odd fails (stable)
            final_pass = (seed_val % 2 == 0)
            if final_pass:
                ds.update_test_run(run_id, {
                    "status": "passed",
                    "logs": ["All steps completed successfully."],
                    "results": {"summary": "Run passed with no errors."},
                })
                self._broadcast("run_status", {"id": run_id, "status": "passed"})
            else:
                ds.update_test_run(run_id, {
                    "status": "failed",
                    "logs": ["A failure occurred in simulated assertion."],
                    "results": {"summary": "Run failed at assertion.", "failed_step": steps},
                })
                self._broadcast("run_status", {"id": run_id, "status": "failed"})
        except Exception as e:
            ds.update_test_run(run_id, {
                "status": "error",
                "logs": [f"Runner error: {e}"],
                "results": {"error": str(e)},
            })
            self._broadcast("run_status", {"id": run_id, "status": "error"})
        finally:
            self._finalize_thread(run_id)

    # PUBLIC_INTERFACE
    def cancel(self, run_id: str) -> bool:
        """
        Request cancellation for an active run. Returns True if a running job was signaled.
        """
        with self._lock:
            evt = self._stop_flags.get(run_id)
            if evt and not evt.is_set():
                evt.set()
                return True
        return False


# Singleton instance for module-level usage
_runner_singleton: Optional[SimulatedRunner] = None
_runner_lock = threading.Lock()


# PUBLIC_INTERFACE
def get_runner() -> SimulatedRunner:
    """Return the singleton SimulatedRunner instance."""
    global _runner_singleton
    if _runner_singleton is None:
        with _runner_lock:
            if _runner_singleton is None:
                _runner_singleton = SimulatedRunner()
    return _runner_singleton
