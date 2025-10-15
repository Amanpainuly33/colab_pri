from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from typing import Set, Dict, Any

from websockets.sync.server import serve

from document_store import DocumentStore


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(threadName)s: %(message)s")


class ClientRegistry:
    """Thread-safe registry of connected clients with IDs."""

    def __init__(self) -> None:
        self._clients: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, ws: Any) -> int:
        with self._lock:
            self._clients[client_id] = ws
            return len(self._clients)

    def remove(self, client_id: str) -> int:
        with self._lock:
            self._clients.pop(client_id, None)
            return len(self._clients)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._clients)


document_store = DocumentStore()
clients = ClientRegistry()


def handle_client(ws: Any) -> None:
    """
    Per-connection handler running in its own thread.

    OS Concepts:
    - Thread-per-client model: Each WebSocket connection is handled by a dedicated thread.
    - Mutual Exclusion: Document operations are protected in DocumentStore.
    - Shared Resource: The document content and client set.
    - Blocking I/O: This thread blocks on ws.send() and message iteration.
    """
    client_id = str(uuid.uuid4())
    num = clients.add(client_id, ws)
    logging.info(f"Client {client_id} connected. Active clients={num}")

    try:
        # On connect, send current document
        content, version = document_store.get_document()
        lock_holder, is_locked = document_store.get_lock_status()
        ws.send(json.dumps({
            "type": "init",
            "client_id": client_id,
            "content": content,
            "version": version,
            "clients": num,
            "lock_holder": lock_holder,
            "is_locked": is_locked,
        }))

        for raw in ws:
            try:
                message: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                ws.send(json.dumps({"type": "error", "message": "invalid_json"}))
                continue

            mtype = message.get("type")
            if mtype == "get_document":
                content, version = document_store.get_document()
                lock_holder, is_locked = document_store.get_lock_status()
                ws.send(json.dumps({
                    "type": "document",
                    "content": content,
                    "version": version,
                    "clients": len(clients.snapshot()),
                    "lock_holder": lock_holder,
                    "is_locked": is_locked,
                }))
            elif mtype == "request_lock":
                acquired = document_store.try_acquire_editor_lock(client_id)
                ws.send(json.dumps({
                    "type": "lock_response",
                    "acquired": acquired,
                    "lock_holder": client_id if acquired else None,
                }))
                if acquired:
                    broadcast(json.dumps({
                        "type": "lock_status",
                        "is_locked": True,
                        "lock_holder": client_id,
                    }), exclude=None)
            elif mtype == "release_lock":
                document_store.release_editor_lock(client_id)
                ws.send(json.dumps({"type": "lock_released"}))
                broadcast(json.dumps({
                    "type": "lock_status",
                    "is_locked": False,
                    "lock_holder": None,
                }), exclude=None)
            elif mtype == "renew_lock":
                renewed = document_store.renew_editor_lock(client_id)
                ws.send(json.dumps({"type": "lock_renewed", "renewed": renewed}))
            elif mtype == "edit":
                lock_holder, is_locked = document_store.get_lock_status()
                if is_locked and lock_holder != client_id:
                    ws.send(json.dumps({
                        "type": "error",
                        "message": "edit_locked",
                        "lock_holder": lock_holder,
                    }))
                    continue

                new_content = message.get("content", "")
                updated_version = document_store.update_document(new_content)
                ws.send(json.dumps({"type": "ack", "version": updated_version}))
                broadcast_payload = json.dumps({
                    "type": "document",
                    "content": new_content,
                    "version": updated_version,
                    "clients": len(clients.snapshot()),
                    "lock_holder": lock_holder,
                    "is_locked": is_locked,
                })
                broadcast(broadcast_payload, exclude=ws)
            else:
                ws.send(json.dumps({"type": "error", "message": "unknown_type"}))

    except Exception as exc:  # noqa: BLE001 broad catch for server stability with logging
        logging.exception("Unhandled error in client handler: %s", exc)
    finally:
        # Release any lock held by this client and notify others
        document_store.release_editor_lock(client_id)
        broadcast(json.dumps({
            "type": "lock_status",
            "is_locked": False,
            "lock_holder": None,
        }), exclude=None)
        num = clients.remove(client_id)
        logging.info(f"Client {client_id} disconnected. Active clients={num}")


def process_request(path: str, request_headers: Dict[str, str]):
    """
    Handle non-WebSocket HTTP requests for platform health checks.

    Render and similar platforms often send HEAD/GET to the root path.
    We return 200 OK for non-upgrade requests so health checks pass.
    Returning None allows WebSocket handshake to proceed for real clients.
    """
    upgrade = request_headers.get("Upgrade", "").lower()
    # Health checks (HEAD/GET) → 200 OK
    if upgrade != "websocket":
        body = b"OK"
        return (
            200,
            [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
            body,
        )
    # Only allow WS upgrades on /ws to avoid collisions with health checks
    if path != "/ws":
        body = b"Not Found"
        return (
            404,
            [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
            body,
        )
    return None


def broadcast(message: str, exclude: Any | None = None) -> None:
    """Send a message to all connected clients except the optional exclude."""
    snapshot = clients.snapshot()
    targets = [ws for ws in snapshot.values() if ws is not exclude]
    for ws in targets:
        try:
            ws.send(message)
        except Exception:
            pass


def safe_send(ws: Any, message: str) -> None:
    try:
        ws.send(message)
    except Exception:
        logging.debug("Failed to send to a client; ignoring (likely disconnected)")


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    with serve(
        handle_client,
        host,
        port,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
        process_request=process_request,
    ) as server:
        logging.info(f"WebSocket server started at ws://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Server shutdown requested by user")


