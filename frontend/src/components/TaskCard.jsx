import { useState } from 'react'
import { Check, Trash2, Clock, Mail, Hexagon, User, ChevronDown, ChevronUp, Folder, Play, RotateCcw, AlertTriangle } from 'lucide-react'

function sourceIcon(source) {
  if (source === 'hera') return <Hexagon size={12} />
  if (source === 'echo') return <Mail size={12} />
  return <User size={12} />
}

function sourceLabel(source) {
  if (source === 'hera') return 'HERA'
  if (source === 'echo') return 'Email'
  return 'Manual'
}

function priorityColor(priority) {
  if (priority === 'urgent') return '#ef4444'
  if (priority === 'high') return '#f59e0b'
  if (priority === 'normal') return 'rgba(255,255,255,0.5)'
  return 'rgba(255,255,255,0.3)'
}

function statusConfig(status) {
  if (status === 'pending') return { label: 'Start', icon: Play, className: 'task-status-start', next: 'in_progress' }
  if (status === 'in_progress') return { label: 'Done', icon: Check, className: 'task-status-done', next: 'completed' }
  if (status === 'completed') return { label: 'Undo', icon: RotateCcw, className: 'task-status-undo', next: 'pending' }
  return { label: 'Start', icon: Play, className: 'task-status-start', next: 'in_progress' }
}

function statusBadge(status) {
  if (status === 'in_progress') return <span className="task-status-badge task-status-in-progress">In Progress</span>
  if (status === 'completed') return <span className="task-status-badge task-status-completed">Done</span>
  return null
}

function isOverdue(task) {
  if (!task.due_date || task.status === 'completed' || task.status === 'dismissed') return false
  return new Date(task.due_date) < new Date()
}

function isApproaching(task) {
  if (!task.due_date || task.status === 'completed' || task.status === 'dismissed') return false
  const deadline = new Date(task.due_date)
  const now = new Date()
  const hoursLeft = (deadline - now) / (1000 * 60 * 60)
  return hoursLeft > 0 && hoursLeft <= 24
}

export default function TaskCard({ task, onUpdate, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const config = statusConfig(task.status)
  const StatusIcon = config.icon
  const overdue = isOverdue(task)
  const approaching = isApproaching(task)

  return (
    <div className={`task-card ${task.status === 'completed' ? 'task-completed' : ''} ${task.status === 'in_progress' ? 'task-in-progress' : ''} ${overdue ? 'task-overdue' : ''} ${approaching ? 'task-approaching' : ''}`}>
      <div className="task-card-header">
        <div className="task-card-left">
          <button
            className={`task-action-btn ${config.className}`}
            onClick={() => onUpdate(task.id, { status: config.next })}
            title={config.label}
          >
            <StatusIcon size={12} />
          </button>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="task-title-row">
              <span className="task-title">{task.title}</span>
              {statusBadge(task.status)}
              {overdue && (
                <span className="task-deadline-badge overdue">
                  <AlertTriangle size={10} /> Overdue
                </span>
              )}
              {approaching && !overdue && (
                <span className="task-deadline-badge approaching">
                  <Clock size={10} /> Due soon
                </span>
              )}
            </div>
            <div className="task-meta">
              <span className="task-source-tag" style={{ color: task.source === 'hera' ? '#8b5cf6' : 'rgba(255,255,255,0.5)' }}>
                {sourceIcon(task.source)} {sourceLabel(task.source)}
              </span>
              {task.metadata?.project_name && (
                <span className="task-project-tag">
                  <Folder size={10} /> {task.metadata.project_name}
                </span>
              )}
              {task.priority !== 'normal' && (
                <span className="task-priority-tag" style={{ color: priorityColor(task.priority) }}>
                  {task.priority}
                </span>
              )}
              {task.due_date && (
                <span className={`task-due ${overdue ? 'task-due-overdue' : ''} ${approaching ? 'task-due-approaching' : ''}`}>
                  <Clock size={10} /> {new Date(task.due_date).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexShrink: 0 }}>
          {task.description && (
            <button className="task-expand-btn" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
          <button className="task-delete-btn" onClick={() => onDelete(task.id)} title="Delete task">
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      {expanded && task.description && (
        <div className="task-description">{task.description}</div>
      )}
      {task.metadata?.email_subject && (
        <div className="task-email-ref">
          From: {task.metadata.email_subject}
        </div>
      )}
    </div>
  )
}
