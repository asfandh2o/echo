import { useAuth } from '../context/AuthContext'
import { LogOut } from 'lucide-react'
import NotificationPanel from './NotificationPanel'

export default function TitleBar({ focusMode, onToggleFocus }) {
  const { logout } = useAuth()

  return (
    <div className="title-bar">
      <div className="title-bar-left">
        <div className="window-dots">
          <span className="dot red" />
          <span className="dot yellow" />
          <span className="dot green" />
        </div>
        <span className="app-title">ECHO</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div className="focus-toggle">
          <span>Focus Mode</span>
          <div
            className={`toggle-switch ${focusMode ? 'active' : ''}`}
            onClick={onToggleFocus}
          />
        </div>
        <NotificationPanel />
        <LogOut
          size={16}
          style={{ color: 'rgba(255,255,255,0.5)', cursor: 'pointer' }}
          onClick={logout}
        />
      </div>
    </div>
  )
}
