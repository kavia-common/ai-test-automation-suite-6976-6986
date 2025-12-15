# ai-test-automation-suite-6976-6986

Realtime updates:
- WebSocket endpoint: ws://<host>/ws (or wss:// if behind TLS)
  - Messages are JSON: { "type": "run_status" | "run_log", "payload": { ... } }
    - run_status payload: { id: "<run_id>", status: "queued|running|passed|failed|error|canceled" }
    - run_log payload: { id: "<run_id>", log: "<line>" }
- SSE fallback: GET /api/test-runs/<id>/events
  - Content-Type: text/event-stream
  - event: <type>, data: {"type":..., "payload": {...}}
  - First event is "hello" with the subscribed run id