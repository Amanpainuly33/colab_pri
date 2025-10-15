from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from document_store import DocumentStore


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class ClientRegistry:
    """Async-safe registry of connected clients with IDs."""

    def __init__(self) -> None:
        self._clients: Dict[str, WebSocket] = {}

    def add(self, client_id: str, ws: WebSocket) -> int:
        self._clients[client_id] = ws
        return len(self._clients)

    def remove(self, client_id: str) -> int:
        self._clients.pop(client_id, None)
        return len(self._clients)

    def snapshot(self) -> Dict[str, WebSocket]:
        return dict(self._clients)


document_store = DocumentStore(lock_timeout=3.0)
clients = ClientRegistry()

app = FastAPI()

# CORS: allow frontend origins to access WebSocket upgrade and health endpoint.
# In production, replace ["*"] with your explicit frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok"})


async def broadcast(message: str, exclude: WebSocket | None = None) -> None:
    snapshot = clients.snapshot()
    targets: List[WebSocket] = [ws for ws in snapshot.values() if ws is not exclude]
    for ws in targets:
        try:
            await ws.send_text(message)
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Async WebSocket endpoint implementing collaborative editing.

    OS Concepts:
    - Shared Resource: The in-memory document content is shared by all clients.
    - Critical Sections: All reads/writes to shared state are guarded by an asyncio.Lock in DocumentStore.
    - Mutual Exclusion: The editor lock provides app-level exclusivity for edits.
    - Non-blocking I/O: All network operations use await to avoid blocking the event loop.
    """
    await ws.accept()
    client_id = str(uuid.uuid4())
    num = clients.add(client_id, ws)
    logging.info(f"Client {client_id} connected. Active clients={num}")

    try:
        content, version = await document_store.get_document()
        lock_holder, is_locked = await document_store.get_lock_status()
        await ws.send_text(json.dumps({
            "type": "init",
            "client_id": client_id,
            "content": content,
            "version": version,
            "clients": num,
            "lock_holder": lock_holder,
            "is_locked": is_locked,
        }))

        while True:
            text = await ws.receive_text()
            try:
                message: Dict[str, Any] = json.loads(text)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "invalid_json"}))
                continue

            mtype = message.get("type")
            if mtype == "get_document":
                content, version = await document_store.get_document()
                lock_holder, is_locked = await document_store.get_lock_status()
                await ws.send_text(json.dumps({
                    "type": "document",
                    "content": content,
                    "version": version,
                    "clients": len(clients.snapshot()),
                    "lock_holder": lock_holder,
                    "is_locked": is_locked,
                }))
            elif mtype == "request_lock":
                acquired = await document_store.try_acquire_editor_lock(client_id)
                await ws.send_text(json.dumps({
                    "type": "lock_response",
                    "acquired": acquired,
                    "lock_holder": client_id if acquired else None,
                }))
                if acquired:
                    await broadcast(json.dumps({
                        "type": "lock_status",
                        "is_locked": True,
                        "lock_holder": client_id,
                    }), exclude=None)
            elif mtype == "release_lock":
                await document_store.release_editor_lock(client_id)
                await ws.send_text(json.dumps({"type": "lock_released"}))
                await broadcast(json.dumps({
                    "type": "lock_status",
                    "is_locked": False,
                    "lock_holder": None,
                }), exclude=None)
            elif mtype == "renew_lock":
                renewed = await document_store.renew_editor_lock(client_id)
                await ws.send_text(json.dumps({"type": "lock_renewed", "renewed": renewed}))
            elif mtype == "edit":
                lock_holder, is_locked = await document_store.get_lock_status()
                if is_locked and lock_holder != client_id:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "edit_locked",
                        "lock_holder": lock_holder,
                    }))
                    continue

                new_content = message.get("content", "")
                updated_version = await document_store.update_document(new_content)
                await ws.send_text(json.dumps({"type": "ack", "version": updated_version}))
                broadcast_payload = json.dumps({
                    "type": "document",
                    "content": new_content,
                    "version": updated_version,
                    "clients": len(clients.snapshot()),
                    "lock_holder": lock_holder,
                    "is_locked": is_locked,
                })
                await broadcast(broadcast_payload, exclude=ws)
            else:
                await ws.send_text(json.dumps({"type": "error", "message": "unknown_type"}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logging.exception("Unhandled error in websocket handler: %s", exc)
    finally:
        await document_store.release_editor_lock(client_id)
        await broadcast(json.dumps({
            "type": "lock_status",
            "is_locked": False,
            "lock_holder": None,
        }), exclude=None)
        num = clients.remove(client_id)
        logging.info(f"Client {client_id} disconnected. Active clients={num}")


def main() -> None:
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run("server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()


