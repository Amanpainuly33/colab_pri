CollabSync Frontend

Setup

1. npm install
2. Configure backend WebSocket URL in `src/useWebSocket.js` (default: ws://localhost:8765/ws)
3. npm run dev

Build

- npm run build

Files

- src/useWebSocket.js: WebSocket hook with auto-reconnect
- src/Editor.jsx: Collaborative editor component
- src/App.jsx: App shell and status UI
- src/main.jsx: Entry point
- index.html: Root HTML


