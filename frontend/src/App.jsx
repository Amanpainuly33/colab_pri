import React from 'react'
import Editor from './Editor.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'
import { useWebSocket } from './useWebSocket.js'

export default function App() {
  const wsApi = useWebSocket()

  return (
    <ErrorBoundary>
      <div style={{ maxWidth: 900, margin: '0 auto', padding: 16 }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h1 style={{ margin: 0 }}>CollabSync</h1>
          <div>
            <button onClick={wsApi.reconnect}>Reconnect</button>
          </div>
        </header>
        <Editor wsApi={wsApi} />
      </div>
    </ErrorBoundary>
  )
}


