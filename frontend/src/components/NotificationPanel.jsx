import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { Bell, X, Check, CheckCheck, Hexagon, Info, Clock, AlertTriangle } from 'lucide-react'

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function sourceIcon(source, type) {
  if (type === 'deadline_overdue') return <AlertTriangle size={14} />
  if (type === 'deadline_reminder') return <Clock size={14} />
  if (source === 'hera') return <Hexagon size={14} />
  return <Info size={14} />
}

function sourceColor(source, type) {
  if (type === 'deadline_overdue') return '#ef4444'
  if (type === 'deadline_reminder') return '#f59e0b'
  if (source === 'hera') return '#8b5cf6'
  return 'rgba(255,255,255,0.5)'
}

export default function NotificationPanel() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const panelRef = useRef(null)

  const fetchCount = async () => {
    try {
      const res = await api.getUnreadCount()
      setUnreadCount(res.count)
    } catch {}
  }

  const fetchNotifications = async () => {
    setLoading(true)
    try {
      const res = await api.listNotifications(false, 30)
      setNotifications(res)
      // Also refresh count
      const countRes = await api.getUnreadCount()
      setUnreadCount(countRes.count)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  // Poll for unread count every 30s
  useEffect(() => {
    fetchCount()
    const interval = setInterval(fetchCount, 30000)
    return () => clearInterval(interval)
  }, [])

  // Load full list when panel opens
  useEffect(() => {
    if (open) fetchNotifications()
  }, [open])

  // Close on click outside
  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const handleMarkRead = async (id) => {
    try {
      await api.markNotificationRead(id)
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, read: true } : n)
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch {}
  }

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead()
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
      setUnreadCount(0)
    } catch {}
  }

  const handleAction = async (notificationId, action) => {
    try {
      await api.executeNotificationAction(notificationId, action)
      setNotifications(prev =>
        prev.map(n =>
          n.id === notificationId
            ? { ...n, action_status: action === 'confirm' ? 'confirmed' : 'dismissed', read: true }
            : n
        )
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (err) {
      console.error('Action failed:', err)
    }
  }

  return (
    <div className="notif-wrap" ref={panelRef}>
      <button
        className="notif-bell"
        onClick={() => setOpen(!open)}
        title="Notifications"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="notif-panel">
          <div className="notif-panel-header">
            <span className="notif-panel-title">Notifications</span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {unreadCount > 0 && (
                <button className="notif-mark-all" onClick={handleMarkAllRead} title="Mark all as read">
                  <CheckCheck size={14} />
                </button>
              )}
              <button className="notif-close" onClick={() => setOpen(false)}>
                <X size={14} />
              </button>
            </div>
          </div>

          <div className="notif-panel-list">
            {loading && notifications.length === 0 && (
              <div className="notif-empty">Loading...</div>
            )}
            {!loading && notifications.length === 0 && (
              <div className="notif-empty">No notifications yet</div>
            )}
            {notifications.map(n => (
              <div
                key={n.id}
                className={`notif-item ${!n.read ? 'notif-unread' : ''} ${n.type === 'deadline_overdue' ? 'notif-deadline-overdue' : ''} ${n.type === 'deadline_reminder' ? 'notif-deadline-reminder' : ''}`}
                onClick={() => !n.read && handleMarkRead(n.id)}
              >
                <div className="notif-item-icon" style={{ color: sourceColor(n.source, n.type) }}>
                  {sourceIcon(n.source, n.type)}
                </div>
                <div className="notif-item-content">
                  <div className="notif-item-title">{n.title}</div>
                  {n.message && <div className="notif-item-msg">{n.message}</div>}
                  <div className="notif-item-meta">
                    <span className="notif-source-tag" style={{ color: sourceColor(n.source) }}>
                      {n.source.toUpperCase()}
                    </span>
                    <span>{timeAgo(n.created_at)}</span>
                  </div>
                  {n.action_type && n.action_status === 'pending' && (
                    <div className="notif-actions">
                      <button
                        className="notif-action-btn notif-action-confirm"
                        onClick={(e) => { e.stopPropagation(); handleAction(n.id, 'confirm') }}
                      >
                        <Check size={12} /> Confirm
                      </button>
                      <button
                        className="notif-action-btn notif-action-dismiss"
                        onClick={(e) => { e.stopPropagation(); handleAction(n.id, 'dismiss') }}
                      >
                        <X size={12} /> Dismiss
                      </button>
                    </div>
                  )}
                  {n.action_status === 'confirmed' && (
                    <span className="notif-action-done" style={{ color: '#22c55e' }}>Confirmed</span>
                  )}
                  {n.action_status === 'dismissed' && (
                    <span className="notif-action-done" style={{ color: 'rgba(255,255,255,0.3)' }}>Dismissed</span>
                  )}
                </div>
                {!n.read && !n.action_type && (
                  <div className="notif-unread-dot" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
