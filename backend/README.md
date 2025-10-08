CollabSync Backend

Requirements

- Python 3.10+
- uv (package/dependency manager)

Setup

1. Install uv: see `https://docs.astral.sh/uv/`
2. Create and activate venv:
   - uv venv
   - source .venv/bin/activate  # Windows: .venv\Scripts\activate
3. Install dependencies:
   - uv pip install websockets

Running

- HOST=0.0.0.0 PORT=8765 python server.py

WebSocket Endpoint

- ws://HOST:PORT/ws

Message Protocol

- Client → Server
  - {"type":"get_document"}
  - {"type":"edit","content":"<full document string>","version":<int>}

- Server → Client
  - {"type":"document","content":"...","version":<int>,"clients":<int>}
  - {"type":"ack","version":<int>}
  - {"type":"error","message":"..."}

Synchronization Strategy

- Document-level mutex (`threading.Lock`) protects critical sections for updates and reads
- Version increment on each successful edit; last-write-wins for MVP
- Broadcast updates to all clients except sender

Deployment Notes

- Generate requirements.txt for platforms expecting pip:
  - uv pip freeze > requirements.txt
- Start command: python server.py


