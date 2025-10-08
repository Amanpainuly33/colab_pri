import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_URL = (import.meta.env.VITE_WS_URL) || 'ws://localhost:8765/ws'

export function useWebSocket(url = DEFAULT_URL) {
  const wsRef = useRef(null)
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const reconnectRef = useRef({ attempts: 0, timer: null })

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }
    setConnectionStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      reconnectRef.current.attempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLastMessage(data)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      scheduleReconnect()
    }

    ws.onerror = () => {
      // Will trigger close in many cases
    }
  }, [url])

  const scheduleReconnect = useCallback(() => {
    const { attempts, timer } = reconnectRef.current
    if (timer) return
    const nextDelay = Math.min(30000, 1000 * Math.pow(2, attempts))
    reconnectRef.current.timer = setTimeout(() => {
      reconnectRef.current.timer = null
      reconnectRef.current.attempts = attempts + 1
      connect()
    }, nextDelay)
  }, [connect])

  const sendMessage = useCallback((obj) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      const ws = wsRef.current
      if (ws) ws.close()
      if (reconnectRef.current.timer) clearTimeout(reconnectRef.current.timer)
    }
  }, [connect])

  return { sendMessage, lastMessage, connectionStatus, reconnect: connect }
}


