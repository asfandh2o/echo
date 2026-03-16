import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import TitleBar from '../components/TitleBar'
import Greeting from '../components/Greeting'
import SummaryCard from '../components/SummaryCard'
import MeetingCard from '../components/MeetingCard'
import EmailCard from '../components/EmailCard'
import TaskCard from '../components/TaskCard'
import DigestNotification from '../components/DigestNotification'
import ChatInput from '../components/ChatInput'
import Toast from '../components/Toast'
import { Loader2, FileText, ListTodo } from 'lucide-react'

export default function Dashboard() {
  const { user } = useAuth()
  const [emails, setEmails] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [events, setEvents] = useState([])
  const [tasks, setTasks] = useState([])
  const [digest, setDigest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [toast, setToast] = useState(null)
  const [focusMode, setFocusMode] = useState(false)
  const [showDigest, setShowDigest] = useState(false)
  const [activeTab, setActiveTab] = useState('messages')

  const showToast = (title, body) => {
    setToast({ title, body })
    setTimeout(() => setToast(null), 4000)
  }

  const loadData = useCallback(async () => {
    try {
      const [emailsRes, suggestionsRes, eventsRes, digestRes, tasksRes] = await Promise.all([
        api.listEmails(0, 10),
        api.listSuggestions('pending', 10),
        api.listEvents(3),
        api.getLatestDigest().catch(() => null),
        api.listTasks().catch(() => []),
      ])
      setEmails(emailsRes)
      setSuggestions(suggestionsRes)
      setEvents(eventsRes)
      setTasks(tasksRes)

      // Auto-regenerate if digest is stale (not from today)
      const today = new Date().toISOString().slice(0, 10)
      if (!digestRes || digestRes.digest_date !== today) {
        try {
          const freshDigest = await api.generateDigest()
          setDigest(freshDigest)
        } catch {
          setDigest(digestRes) // fallback to stale digest
        }
      } else {
        setDigest(digestRes)
      }
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Poll tasks every 5s for real-time sync with HERA
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const freshTasks = await api.listTasks().catch(() => [])
        setTasks(freshTasks)
      } catch {}
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  // Auto-show digest notification when digest loads
  useEffect(() => {
    if (digest && !loading) {
      setShowDigest(true)
    }
  }, [digest, loading])

  const handleFetchEmails = async () => {
    setFetching(true)
    try {
      const result = await api.fetchEmails(10)
      if (result.new > 0) {
        showToast('New Emails', `${result.new} new email(s) processed`)
        await loadData()
      } else {
        showToast('Up to date', 'No new emails found')
      }
    } catch (err) {
      showToast('Error', err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleTaskUpdate = async (taskId, updates) => {
    try {
      const updated = await api.updateTask(taskId, updates)
      setTasks(prev => prev.map(t => t.id === taskId ? updated : t))
    } catch (err) {
      showToast('Error', err.message)
    }
  }

  const handleTaskDelete = async (taskId) => {
    try {
      await api.deleteTask(taskId)
      setTasks(prev => prev.filter(t => t.id !== taskId))
    } catch (err) {
      showToast('Error', err.message)
    }
  }

  const pendingSuggestions = suggestions.filter(s => s.status === 'pending')
  const urgentEmails = emails.filter(e => e.classification?.urgent)
  const needsResponse = emails.filter(e => e.classification?.needs_response)
  const activeTasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'dismissed')
  const completedTasks = tasks.filter(t => t.status === 'completed')

  // Build suggestion map: email_id -> suggestion
  const suggestionMap = {}
  for (const s of suggestions) {
    suggestionMap[s.email_id] = s
  }

  // Find next upcoming meeting
  const nextMeeting = events.length > 0 ? events[0] : null

  if (loading) {
    return (
      <div className="app-container">
        <TitleBar focusMode={focusMode} onToggleFocus={() => setFocusMode(!focusMode)} />
        <div className="content-area">
          <div className="loading-container">
            <div className="spinner" />
            <div className="loading-text">Loading your dashboard...</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <TitleBar focusMode={focusMode} onToggleFocus={() => setFocusMode(!focusMode)} />

      <div className="content-area">
        <Greeting email={user?.email} />

        <SummaryCard
          totalEmails={emails.length}
          urgentCount={urgentEmails.length}
          pendingSuggestions={pendingSuggestions.length}
          needsResponse={needsResponse.length}
          onRefresh={handleFetchEmails}
          fetching={fetching}
        />

        {/* Digest button to re-open the notification */}
        {digest && !showDigest && (
          <button className="btn btn-secondary" onClick={() => setShowDigest(true)} style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, width: 'fit-content' }}>
            <FileText size={13} /> View Daily Digest
          </button>
        )}

        {/* Tab bar */}
        <div className="tab-bar">
          <button
            className={`tab-btn ${activeTab === 'messages' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('messages')}
          >
            Messages
          </button>
          <button
            className={`tab-btn ${activeTab === 'tasks' ? 'tab-active' : ''}`}
            onClick={() => setActiveTab('tasks')}
          >
            Tasks
            {activeTasks.length > 0 && (
              <span className="tab-badge">{activeTasks.length}</span>
            )}
          </button>
        </div>

        {/* Messages tab */}
        {activeTab === 'messages' && (
          <>
            {nextMeeting && (
              <MeetingCard event={nextMeeting} />
            )}

            {emails.slice(0, focusMode ? 3 : 6).map(email => (
              <EmailCard
                key={email.id}
                email={email}
                suggestion={suggestionMap[email.id]}
                onSuggestionHandled={(id) => {
                  setSuggestions(prev => prev.filter(s => s.id !== id))
                }}
              />
            ))}

            {emails.length === 0 && (
              <div className="empty-state">
                <p>No emails yet. Click refresh to fetch your latest emails.</p>
              </div>
            )}
          </>
        )}

        {/* Tasks tab */}
        {activeTab === 'tasks' && (
          <>
            {activeTasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onUpdate={handleTaskUpdate}
                onDelete={handleTaskDelete}
              />
            ))}

            {completedTasks.length > 0 && (
              <>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 12 }}>
                  Completed
                </div>
                {completedTasks.slice(0, 5).map(task => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onUpdate={handleTaskUpdate}
                    onDelete={handleTaskDelete}
                  />
                ))}
              </>
            )}

            {tasks.length === 0 && (
              <div className="empty-state">
                <ListTodo size={32} style={{ opacity: 0.3 }} />
                <p>No tasks yet. Tasks will appear here when extracted from emails or assigned in HERA.</p>
              </div>
            )}
          </>
        )}
      </div>

      <ChatInput onRefresh={handleFetchEmails} fetching={fetching} />

      {toast && <Toast title={toast.title} body={toast.body} />}

      <DigestNotification
        digest={digest}
        onRefresh={loadData}
        visible={showDigest}
        onDismiss={() => setShowDigest(false)}
      />
    </div>
  )
}
