from __future__ import annotations

import json
import logging
import os
import threading
from typing import Set, Dict, Any

from websockets.sync.server import serve

from document_store import DocumentStore


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(threadName)s: %(message)s")


class ClientRegistry:
    """Thread-safe registry of connected clients."""

    def __init__(self) -> None:
        self._clients: Set[Any] = set()
        self._lock = threading.Lock()

    def add(self, ws: Any) -> int:
        with self._lock:
            self._clients.add(ws)
            return len(self._clients)

    def remove(self, ws: Any) -> int:
        with self._lock:
            self._clients.discard(ws)
            return len(self._clients)

    def snapshot(self) -> Set[Any]:
        with self._lock:
            return set(self._clients)


document_store = DocumentStore()
clients = ClientRegistry()


def handle_client(ws: Any) -> None:
    """
    Per-connection handler.

    OS Concepts:
    - Multi-threading model: We keep single asyncio loop but emulate thread-per-client via tasks.
      In classic OS terms, each client is handled concurrently; critical sections are guarded.
    - Mutual Exclusion: Document operations are protected in DocumentStore.
    - Shared Resource: The document content and client set.
    """
    num = clients.add(ws)
    logging.info(f"Client connected. Active clients={num}")

    try:
        # On connect, send current document
        content, version = document_store.get_document()
        ws.send(json.dumps({
            "type": "document",
            "content": content,
            "version": version,
            "clients": num,
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
                ws.send(json.dumps({
                    "type": "document",
                    "content": content,
                    "version": version,
                    "clients": len(clients.snapshot()),
                }))
            elif mtype == "edit":
                new_content = message.get("content", "")
                # Last-write-wins MVP
                updated_version = document_store.update_document(new_content)
                ws.send(json.dumps({"type": "ack", "version": updated_version}))

                # Broadcast to all except sender
                broadcast_payload = json.dumps({
                    "type": "document",
                    "content": new_content,
                    "version": updated_version,
                    "clients": len(clients.snapshot()),
                })
                broadcast(broadcast_payload, exclude=ws)
            else:
                ws.send(json.dumps({"type": "error", "message": "unknown_type"}))

    except Exception as exc:  # noqa: BLE001 broad catch for server stability with logging
        logging.exception("Unhandled error in client handler: %s", exc)
    finally:
        num = clients.remove(ws)
        logging.info(f"Client disconnected. Active clients={num}")


def broadcast(message: str, exclude: Any | None = None) -> None:
    """Send a message to all connected clients except the optional exclude."""
    targets = [c for c in clients.snapshot() if c is not exclude]
    for c in targets:
        try:
            c.send(message)
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
    with serve(handle_client, host, port, ping_interval=20, ping_timeout=20, max_size=2**20) as server:
        logging.info(f"WebSocket server started at ws://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Server shutdown requested by user")


