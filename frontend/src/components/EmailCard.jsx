import { useState } from 'react'
import { Send, X, Check, Edit3, Loader2 } from 'lucide-react'
import { api } from '../api'

export default function EmailCard({ email, suggestion, onSuggestionHandled }) {
  const [mode, setMode] = useState('view') // 'view' | 'editing' | 'sending' | 'sent' | 'rejected'
  const [editText, setEditText] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  const receivedAt = new Date(email.received_at)
  const timeStr = receivedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  const senderName = email.sender?.split('<')[0]?.trim() || email.sender
  const category = email.classification?.category
  const isUrgent = email.classification?.urgent

  const handleAccept = async () => {
    if (!suggestion) return
    setLoading(true)
    try {
      await api.submitFeedback(suggestion.id, {
        feedback_type: 'accepted',
        final_text: suggestion.suggestion_text,
      })
      setMode('sent')
      setStatusMsg('Reply sent!')
      onSuggestionHandled?.(suggestion.id)
    } catch (err) {
      setStatusMsg(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleReject = () => {
    setEditText('')
    setMode('editing')
  }

  const handleSendEdited = async () => {
    if (!editText.trim() || !suggestion) return
    setLoading(true)
    try {
      await api.submitFeedback(suggestion.id, {
        feedback_type: 'rejected',
        final_text: editText.trim(),
      })
      setMode('sent')
      setStatusMsg('Your response was sent & ECHO will learn from your style.')
      onSuggestionHandled?.(suggestion.id)
    } catch (err) {
      setStatusMsg(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="email-card">
      <div className="email-header">
        <span className="email-sender">{senderName}</span>
        <span className="email-time">{timeStr}</span>
      </div>
      <div className="email-subject">{email.subject || '(no subject)'}</div>
      {email.body && (
        <div className="email-preview">{email.body.slice(0, 150)}</div>
      )}

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
        {isUrgent && <span className="email-badge badge-urgent">Urgent</span>}
        {category && (
          <span className={`email-badge badge-${category === 'work' ? 'work' : 'meeting'}`}>
            {category}
          </span>
        )}
      </div>

      {suggestion && mode === 'view' && (
        <div className="suggestion-box">
          <div className="suggestion-label">Suggested Reply</div>
          <div className="suggestion-text">"{suggestion.suggestion_text}"</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
            <button
              className="btn btn-success"
              style={{ fontSize: 11, padding: '7px 14px', flex: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
              onClick={handleAccept}
              disabled={loading}
            >
              {loading ? <Loader2 size={12} className="spin" /> : <Send size={12} />}
              Accept & Send
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: '7px 14px', flex: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
              onClick={handleReject}
            >
              <Edit3 size={12} /> Write My Own
            </button>
          </div>
        </div>
      )}

      {suggestion && mode === 'editing' && (
        <div className="suggestion-box" style={{ borderColor: 'rgba(74, 108, 247, 0.3)' }}>
          <div className="suggestion-label">Write your response</div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            ECHO will learn from your tone for future suggestions
          </p>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            placeholder="Type your reply here..."
            style={{
              width: '100%',
              minHeight: 80,
              padding: '10px 12px',
              border: '1px solid rgba(74, 108, 247, 0.2)',
              borderRadius: 8,
              fontSize: 13,
              fontFamily: 'inherit',
              resize: 'vertical',
              outline: 'none',
              background: 'rgba(255,255,255,0.6)',
              color: 'var(--text-primary)',
            }}
          />
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button
              className="btn btn-primary"
              style={{ fontSize: 11, padding: '7px 14px', flex: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
              onClick={handleSendEdited}
              disabled={loading || !editText.trim()}
            >
              {loading ? <Loader2 size={12} className="spin" /> : <Send size={12} />}
              Send & Learn
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: '7px 14px', flex: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
              onClick={() => setMode('view')}
            >
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      )}

      {mode === 'sent' && (
        <div className="calendar-indicator">
          <Check size={14} />
          <span>{statusMsg}</span>
        </div>
      )}

      {statusMsg && mode !== 'sent' && (
        <p style={{ fontSize: 11, color: 'var(--danger)', marginTop: 6 }}>{statusMsg}</p>
      )}
    </div>
  )
}
