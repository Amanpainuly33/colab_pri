import React, { useEffect, useMemo, useRef, useState } from 'react'

export default function Editor({ wsApi }) {
  const { sendMessage, lastMessage, connectionStatus } = wsApi
  const [content, setContent] = useState('')
  const [version, setVersion] = useState(0)
  const [clients, setClients] = useState(1)
  const [syncStatus, setSyncStatus] = useState('synced')
  const textareaRef = useRef(null)
  const debounceTimer = useRef(null)

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'document') {
      // Preserve cursor when applying updates
      const el = textareaRef.current
      const start = el ? el.selectionStart : 0
      const end = el ? el.selectionEnd : 0
      setContent(lastMessage.content)
      setVersion(lastMessage.version)
      setClients(lastMessage.clients || clients)
      setSyncStatus('synced')
      // Restore cursor after state flush
      requestAnimationFrame(() => {
        if (el) {
          el.selectionStart = start
          el.selectionEnd = end
        }
      })
    } else if (lastMessage.type === 'ack') {
      setVersion(lastMessage.version)
      setSyncStatus('synced')
    } else if (lastMessage.type === 'error') {
      setSyncStatus('error')
    }
  }, [lastMessage])

  const onChange = (e) => {
    const next = e.target.value
    setContent(next)
    setSyncStatus('pending')
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      sendMessage({ type: 'edit', content: next, version })
    }, 300)
  }

  const statusColor = useMemo(() => {
    if (connectionStatus === 'connecting') return '#eab308' // yellow
    if (connectionStatus === 'connected') return '#22c55e' // green
    return '#ef4444' // red
  }, [connectionStatus])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 10, height: 10, borderRadius: 9999, background: statusColor }} />
        <span>Connection: {connectionStatus}</span>
        <span>Version: {version}</span>
        <span>Users: {clients}</span>
        <span>Sync: {syncStatus}</span>
      </div>
      <textarea
        ref={textareaRef}
        value={content}
        onChange={onChange}
        style={{ width: '100%', minHeight: 300, fontFamily: 'monospace', fontSize: 14, padding: 12 }}
        placeholder="Start typing..."
      />
    </div>
  )
}


