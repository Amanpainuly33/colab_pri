CollabSync

Overview

CollabSync is a real-time multi-threaded collaborative text editor demonstrating OS concepts like multi-threading, synchronization, shared memory management, and socket communication. It consists of a Python WebSocket backend and a React frontend.

Quick Start

- Backend
  - cd backend
  - uv venv && source .venv/bin/activate
  - uv pip install -r requirements.txt || uv pip install websockets
  - HOST=0.0.0.0 PORT=8765 python server.py

- Frontend
  - cd frontend
  - npm install
  - npm run dev

Testing checklist

- Single client edits reflect instantly
- Two+ browser tabs update each other
- Disconnect a tab; remaining stay stable; reconnect resumes sync

Demo steps

1) Start backend on :8765
2) Start frontend dev server
3) Open two tabs to the frontend
4) Type in one tab; watch updates in the other
5) Kill backend then restart; verify frontend reconnects

Architecture

- Backend: Python websockets server, thread-per-client, mutex-protected in-memory document store with versioning.
- Frontend: React app using a WebSocket hook to send/receive document updates and render an editor.

Deployment

- Backend: Render/Railway; start command: python server.py; env: HOST, PORT
- Frontend: Vercel/Netlify; configure WebSocket URL in useWebSocket.js

See backend/README.md and frontend/README.md for details.


