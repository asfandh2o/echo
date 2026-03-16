import { useState } from 'react'
import { Send, Loader2, Check, Edit3, X, Users, CalendarCheck, Clock, AlertCircle } from 'lucide-react'
import { api } from '../api'

export default function ChatInput({ onRefresh, fetching }) {
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [reply, setReply] = useState(null)
  const [emailDraft, setEmailDraft] = useState(null)
  const [contactOptions, setContactOptions] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const [editDraft, setEditDraft] = useState({})
  const [sending, setSending] = useState(false)
  const [sendStatus, setSendStatus] = useState(null)
  const [calendarEvent, setCalendarEvent] = useState(null)
  const [calendarResult, setCalendarResult] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!message.trim() || loading) return

    const lower = message.toLowerCase()
    if (lower.includes('fetch') || lower.includes('refresh') || lower.includes('check email')) {
      onRefresh()
      setMessage('')
      return
    }

    setLoading(true)
    setReply(null)
    setEmailDraft(null)
    setContactOptions(null)
    setSendStatus(null)
    setEditMode(false)
    setCalendarResult(null)
    try {
      const result = await api.sendChatMessage(message)
      if (result.calendar_event) {
        setCalendarResult(result.calendar_event)
        setReply(result.reply)
      } else if (result.email_draft) {
        setEmailDraft(result.email_draft)
        setEditDraft({ ...result.email_draft })
        setReply(result.reply)
        if (result.contact_options?.length > 0) {
          setContactOptions(result.contact_options)
        }
      } else {
        setReply(result.reply)
      }
      setMessage('')
    } catch (err) {
      setReply('Sorry, something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleContactSelect = (email) => {
    setEmailDraft(prev => ({ ...prev, to: email }))
    setEditDraft(prev => ({ ...prev, to: email }))
    setContactOptions(null)
  }

  const handleSendDraft = async () => {
    const draft = editMode ? editDraft : emailDraft
    if (!draft?.to || !draft?.body) return
    setSending(true)
    setSendStatus(null)
    try {
      const result = await api.sendDraftEmail({
        to: draft.to,
        subject: draft.subject,
        body: draft.body,
      })
      setSendStatus(result.status === 'sent' ? 'sent' : 'error')
      if (result.calendar_event_created) {
        setCalendarEvent(result.calendar_event_created)
      }
    } catch {
      setSendStatus('error')
    } finally {
      setSending(false)
    }
  }

  const handleDismiss = () => {
    setEmailDraft(null)
    setContactOptions(null)
    setReply(null)
    setEditMode(false)
    setSendStatus(null)
  }

  return (
    <div className="chat-input-area">
      {/* Calendar event result card */}
      {calendarResult && (
        <div className="chat-draft-card">
          <div className="chat-draft-header">
            <span className="chat-reply-label">ECHO — Calendar</span>
            <button className="chat-draft-close" onClick={() => { setCalendarResult(null); setReply(null) }}>
              <X size={14} />
            </button>
          </div>
          {calendarResult.status === 'created' ? (
            <div>
              <div className="chat-draft-success">
                <CalendarCheck size={14} />
                <span>Event created!</span>
              </div>
              <div className="chat-calendar-details">
                <div className="chat-draft-field">
                  <span className="chat-draft-label">Event</span>
                  <span className="chat-draft-value">{calendarResult.summary}</span>
                </div>
                {calendarResult.attendees?.length > 0 && (
                  <div className="chat-draft-field">
                    <span className="chat-draft-label">Invited</span>
                    <span className="chat-draft-value">{calendarResult.attendees.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
          ) : calendarResult.status === 'conflict' ? (
            <div>
              <div className="chat-calendar-conflict">
                <AlertCircle size={14} />
                <span>Time conflict detected</span>
              </div>
              <p className="chat-reply-text" style={{ marginTop: 8 }}>{reply}</p>
            </div>
          ) : calendarResult.status === 'already_scheduled' ? (
            <div>
              <div className="chat-draft-calendar">
                <CalendarCheck size={14} />
                <span>Already on your calendar</span>
              </div>
            </div>
          ) : (
            <div>
              <div className="chat-calendar-conflict">
                <AlertCircle size={14} />
                <span>{calendarResult.message || 'Something went wrong'}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Normal text reply (no draft, no calendar) */}
      {reply && !emailDraft && !calendarResult && (
        <div className="chat-reply" onClick={() => setReply(null)}>
          <span className="chat-reply-label">ECHO</span>
          <p className="chat-reply-text">{reply}</p>
        </div>
      )}

      {/* Email draft card */}
      {emailDraft && (
        <div className="chat-draft-card">
          <div className="chat-draft-header">
            <span className="chat-reply-label">ECHO — Draft Email</span>
            <button className="chat-draft-close" onClick={handleDismiss}>
              <X size={14} />
            </button>
          </div>

          {sendStatus === 'sent' ? (
            <div>
              <div className="chat-draft-success">
                <Check size={14} />
                <span>Email sent successfully!</span>
              </div>
              {calendarEvent && calendarEvent !== 'already on calendar' && (
                <div className="chat-draft-calendar">
                  <CalendarCheck size={14} />
                  <span>Calendar event created: {calendarEvent}</span>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Contact picker when multiple matches found */}
              {contactOptions && (
                <div className="chat-contact-picker">
                  <div className="chat-contact-picker-label">
                    <Users size={12} />
                    <span>Multiple contacts found — select one:</span>
                  </div>
                  {contactOptions.map((c) => (
                    <button
                      key={c.email}
                      className="chat-contact-option"
                      onClick={() => handleContactSelect(c.email)}
                    >
                      <span className="chat-contact-name">{c.name}</span>
                      <span className="chat-contact-email">{c.email}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="chat-draft-field">
                <span className="chat-draft-label">To</span>
                {editMode ? (
                  <input
                    className="chat-draft-input"
                    value={editDraft.to}
                    onChange={(e) => setEditDraft({ ...editDraft, to: e.target.value })}
                  />
                ) : (
                  <span className="chat-draft-value">{emailDraft.to || '(not specified)'}</span>
                )}
              </div>
              <div className="chat-draft-field">
                <span className="chat-draft-label">Subject</span>
                {editMode ? (
                  <input
                    className="chat-draft-input"
                    value={editDraft.subject}
                    onChange={(e) => setEditDraft({ ...editDraft, subject: e.target.value })}
                  />
                ) : (
                  <span className="chat-draft-value">{emailDraft.subject}</span>
                )}
              </div>
              <div className="chat-draft-field">
                <span className="chat-draft-label">Body</span>
                {editMode ? (
                  <textarea
                    className="chat-draft-textarea"
                    value={editDraft.body}
                    onChange={(e) => setEditDraft({ ...editDraft, body: e.target.value })}
                  />
                ) : (
                  <p className="chat-draft-body">{emailDraft.body}</p>
                )}
              </div>

              {sendStatus === 'error' && (
                <p style={{ fontSize: 11, color: '#ef4444', marginTop: 6 }}>
                  Failed to send. Please try again.
                </p>
              )}

              <div className="chat-draft-actions">
                <button
                  className="chat-draft-btn chat-draft-btn-send"
                  onClick={handleSendDraft}
                  disabled={sending}
                >
                  {sending ? <Loader2 size={12} className="spin" /> : <Send size={12} />}
                  Send
                </button>
                {!editMode ? (
                  <button
                    className="chat-draft-btn chat-draft-btn-alter"
                    onClick={() => setEditMode(true)}
                  >
                    <Edit3 size={12} /> Alter
                  </button>
                ) : (
                  <button
                    className="chat-draft-btn chat-draft-btn-alter"
                    onClick={() => { setEditMode(false); setEditDraft({ ...emailDraft }) }}
                  >
                    <X size={12} /> Cancel
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}

      <form className="chat-input-wrapper" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          type="text"
          placeholder="Ask ECHO anything about your inbox..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={fetching || loading}
        />
        <button type="submit" className="chat-send-btn" disabled={fetching || loading}>
          {loading ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  )
}
