import React, { useEffect, useMemo, useRef, useState } from 'react'

export default function Editor({ wsApi }) {
  const { sendMessage, lastMessage, connectionStatus, clientId } = wsApi
  const [content, setContent] = useState('')
  const [version, setVersion] = useState(0)
  const [clients, setClients] = useState(1)
  const [syncStatus, setSyncStatus] = useState('synced')
  const [isLocked, setIsLocked] = useState(false)
  const [lockHolder, setLockHolder] = useState(null)
  const [hasLock, setHasLock] = useState(false)
  const textareaRef = useRef(null)
  const debounceTimer = useRef(null)
  const lockRenewalTimer = useRef(null)

  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.type === 'init' || lastMessage.type === 'document') {
      // Preserve cursor when applying updates
      const el = textareaRef.current
      const start = el ? el.selectionStart : 0
      const end = el ? el.selectionEnd : 0
      setContent(lastMessage.content)
      setVersion(lastMessage.version)
      setClients(lastMessage.clients || clients)
      setIsLocked(lastMessage.is_locked || false)
      setLockHolder(lastMessage.lock_holder || null)
      setSyncStatus('synced')
      if (clientId && lastMessage.lock_holder === clientId) {
        setHasLock(True)
      } else if (lastMessage.lock_holder !== clientId) {
        setHasLock(false)
      }
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
    } else if (lastMessage.type === 'lock_response') {
      if (lastMessage.acquired) {
        setHasLock(true)
        setIsLocked(true)
        setLockHolder(clientId)
        startLockRenewal()
      }
    } else if (lastMessage.type === 'lock_released') {
      setHasLock(false)
      stopLockRenewal()
    } else if (lastMessage.type === 'lock_status') {
      setIsLocked(lastMessage.is_locked)
      setLockHolder(lastMessage.lock_holder)
      if (lastMessage.lock_holder !== clientId) {
        setHasLock(false)
        stopLockRenewal()
      }
    } else if (lastMessage.type === 'error') {
      setSyncStatus('error')
      if (lastMessage.message === 'edit_locked') {
        requestLock()
      }
    }
  }, [lastMessage, clientId, clients])

  const startLockRenewal = () => {
    stopLockRenewal()
    lockRenewalTimer.current = setInterval(() => {
      sendMessage({ type: 'renew_lock' })
    }, 2000)
  }

  const stopLockRenewal = () => {
    if (lockRenewalTimer.current) {
      clearInterval(lockRenewalTimer.current)
      lockRenewalTimer.current = null
    }
  }

  const requestLock = () => {
    sendMessage({ type: 'request_lock' })
  }

  const releaseLock = () => {
    sendMessage({ type: 'release_lock' })
    setHasLock(false)
    stopLockRenewal()
  }

  const onChange = (e) => {
    const next = e.target.value
    if (!canEdit) {
      requestLock()
      return
    }
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
        <span>{isLocked ? (hasLock ? 'You have edit control' : 'Locked by another user') : 'Unlocked'}</span>
        {hasLock && (
          <button onClick={releaseLock} style={{ padding: '4px 8px', fontSize: '12px' }}>Release Lock</button>
        )}
      </div>
      <textarea
        ref={textareaRef}
        value={content}
        onChange={onChange}
        onFocus={() => { if (!hasLock && !isLocked) requestLock() }}
        onBlur={() => { setTimeout(() => { if (hasLock) releaseLock() }, 1000) }}
        disabled={!canEdit}
        style={{ width: '100%', minHeight: 300, fontFamily: 'monospace', fontSize: 14, padding: 12, opacity: canEdit ? 1 : 0.6, cursor: canEdit ? 'text' : 'not-allowed' }}
        placeholder={canEdit ? "Start typing..." : "Waiting for edit control..."}
      />
      {!canEdit && (
        <div style={{ padding: 12, background: '#fee', border: '1px solid #fcc', borderRadius: 6, color: '#c00' }}>
          Another user is currently editing. The editor will unlock automatically when they're done.
        </div>
      )}
    </div>
  )
}


