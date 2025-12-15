from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional, Set, Iterable

from flask import Blueprint, Response, stream_with_context
from flask_cors import cross_origin

try:
    # Flask-Sock provides WebSocket support for Flask 2/3
    from flask_sock import Sock  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    Sock = None  # type: ignore

from .services.runner import BroadcastEvent

# A global in-memory pub-sub for run events. Thread-safe for the simulated runner usage.
class _EventHub:
    """
    Keeps track of WebSocket clients and SSE subscribers and broadcasts events to them.

    - WebSocket clients receive JSON frames.
    - SSE subscribers receive text/event-stream formatted messages.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ws_clients: Set[Any] = set()       # objects with .send(str) and .closed property
        self._sse_queues: Set["threading.Condition"] = set()
        self._sse_buffers: Dict[int, list[str]] = {}
        self._next_sse_id = 1

    def add_ws(self, ws: Any) -> None:
        with self._lock:
            self._ws_clients.add(ws)

    def remove_ws(self, ws: Any) -> None:
        with self._lock:
            self._ws_clients.discard(ws)

    def add_sse(self) -> int:
        """
        Register a new SSE subscriber. Returns a subscriber id used to pull frames.
        """
        with self._lock:
            sub_id = self._next_sse_id
            self._next_sse_id += 1
            cond = threading.Condition()
            self._sse_queues.add(cond)
            self._sse_buffers[sub_id] = []
            return sub_id

    def remove_sse(self, sub_id: int) -> None:
        with self._lock:
            self._sse_buffers.pop(sub_id, None)
            # Can't remove specific Condition by id; safe to leave. GC when generator exits.

    def _notify_sse(self, frame: str) -> None:
        """
        Append frame to all subscriber buffers and notify.
        """
        with self._lock:
            for sub_id in list(self._sse_buffers.keys()):
                self._sse_buffers[sub_id].append(frame)
            for cond in list(self._sse_queues):
                try:
                    with cond:
                        cond.notify_all()
                except Exception:
                    # ignore broken/notified conditions, they will be GC'd with request
                    pass

    def _serialize_ws(self, event: BroadcastEvent) -> str:
        return json.dumps({"type": event.type, "payload": event.payload})

    def _serialize_sse(self, event: BroadcastEvent) -> str:
        # Server-Sent Events frame; type field used as 'event:' for client filtering
        data = json.dumps({"type": event.type, "payload": event.payload})
        return f"event: {event.type}\ndata: {data}\n\n"

    # PUBLIC_INTERFACE
    def broadcast(self, event: BroadcastEvent) -> None:
        """Broadcast an event to all WebSocket and SSE subscribers."""
        message = self._serialize_ws(event)
        sse_frame = self._serialize_sse(event)
        # Send to websockets
        with self._lock:
            dead_ws: Set[Any] = set()
            for ws in list(self._ws_clients):
                try:
                    # flask-sock websocket .send() expects str for text frames
                    ws.send(message)
                except Exception:
                    dead_ws.add(ws)
            for ws in dead_ws:
                self._ws_clients.discard(ws)
        # Send to SSE
        self._notify_sse(sse_frame)

    # PUBLIC_INTERFACE
    def pull_sse_frames(self, sub_id: int) -> Iterable[str]:
        """
        Generator that yields SSE frames for the subscriber with sub_id.
        Blocks until new frames are available, then yields them.
        """
        # Each subscriber uses its own Condition to block/wake.
        cond = threading.Condition()

        with self._lock:
            self._sse_queues.add(cond)

        try:
            while True:
                # Yield pending frames if any
                flush: Optional[list[str]] = None
                with self._lock:
                    buf = self._sse_buffers.get(sub_id, [])
                    if buf:
                        flush = buf[:]
                        self._sse_buffers[sub_id] = []
                if flush:
                    for frame in flush:
                        yield frame
                    continue

                # Otherwise, wait for notification
                with cond:
                    cond.wait(timeout=15.0)
        finally:
            # Cleanup subscriber buffer on exit
            self.remove_sse(sub_id)

# Singleton hub
event_hub = _EventHub()

# Flask Blueprint for SSE endpoint, since WebSocket is not part of Smorest.
realtime_blp = Blueprint("Realtime", __name__, url_prefix="")

# Initialize Sock if available; will be attached by app factory
sock: Optional[Sock] = None

def init_app_for_realtime(flask_app) -> None:
    """
    Initialize WebSocket (if Flask-Sock installed) and register SSE routes.
    Also expose a broadcaster function to wire into the runner.
    """
    global sock
    # Register SSE endpoint
    flask_app.register_blueprint(realtime_blp)

    # Attach Sock if Flask-Sock is available
    if Sock is not None:
        sock = Sock(flask_app)

    # PUBLIC_INTERFACE
    def broadcaster(event: BroadcastEvent) -> None:
        """
        Broadcaster function to be passed to the runner; it publishes events to subscribers.
        """
        event_hub.broadcast(event)

    # Return via app config for import-free access if needed
    flask_app.config["RUNNER_BROADCASTER"] = broadcaster


# ---------- WebSocket endpoint (if Flask-Sock present) ----------

if Sock is not None:
    # PUBLIC_INTERFACE
    def register_ws_routes(s: Sock) -> None:
        """
        Register WebSocket endpoint for real-time run events.
        """
        @s.route("/ws")
        def ws(ws):  # type: ignore
            """
            WebSocket endpoint that streams run events in real-time.

            Clients connect to ws://<host>/ws and receive JSON messages:
              { "type": "<event_type>", "payload": { ... } }

            Event types include: "run_status" and "run_log".
            """
            # Track client
            event_hub.add_ws(ws)
            try:
                # We support one-way server->client. However, to keep the
                # connection alive and handle potential client pings, read loop is present.
                while True:
                    try:
                        # Non-blocking receive; if client sends 'ping' we ignore.
                        msg = ws.receive(timeout=30)
                        if msg is None:
                            # Client disconnected
                            break
                    except Exception:
                        # Periodically loop; presence of exception means no message within timeout.
                        # Keep the connection open to push server events.
                        pass
            finally:
                event_hub.remove_ws(ws)
else:
    def register_ws_routes(_: Any) -> None:  # pragma: no cover - no websocket runtime
        return None


# ---------- SSE fallback endpoint ----------

@realtime_blp.route("/api/test-runs/<string:run_id>/events", methods=["GET"])
@cross_origin(origins="*")
def sse_events(run_id: str):
    """
    Server-Sent Events endpoint for a specific run.
    Clients can connect via:
      GET /api/test-runs/<id>/events
    and should set EventSource on the frontend.

    Each message has event: <type> and data: {"type":..., "payload": {...}}.
    """
    # For simplicity, we currently broadcast to all subscribers; frontend can filter by id.
    # Future enhancement: filter on hub side by run_id.
    sub_id = event_hub.add_sse()

    @stream_with_context
    def generate():
        # Send an initial hello so clients know the stream is alive
        hello = json.dumps({"type": "hello", "payload": {"run_id": run_id, "note": "subscribed"}})
        yield f"event: hello\ndata: {hello}\n\n"
        # Stream frames from hub
        for frame in event_hub.pull_sse_frames(sub_id):
            yield frame

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
    }
    return Response(generate(), headers=headers)
