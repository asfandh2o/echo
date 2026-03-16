import { useState } from 'react'
import { FileText, AlertTriangle, Mail, MessageSquare, RefreshCw, Loader2 } from 'lucide-react'
import { api } from '../api'

export default function DigestCard({ digest, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.generateDigest()
      onRefresh?.()
    } catch (err) {
      console.error('Failed to generate digest:', err)
    } finally {
      setRefreshing(false)
    }
  }

  if (!digest) {
    return (
      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileText size={15} />
          Daily Digest
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '8px 0' }}>
          No digest available yet.
        </p>
        <div className="card-actions">
          <button className="btn btn-primary" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? (
              <><Loader2 size={14} style={{ display: 'inline', marginRight: 6, animation: 'spin 1s linear infinite' }} /> Generating...</>
            ) : (
              <><RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} /> Generate Digest</>
            )}
          </button>
        </div>
      </div>
    )
  }

  const { content, llm_summary } = digest
  const categories = content?.category_breakdown || {}
  const urgentEmails = content?.urgent_emails || []
  const suggestions = content?.suggestions_summary || {}
  const digestDate = new Date(digest.digest_date + 'T00:00:00')
  const dateStr = digestDate.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileText size={15} />
          Daily Digest
        </h3>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{dateStr}</span>
      </div>

      {llm_summary && (
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: '8px 0 12px' }}>
          {llm_summary}
        </p>
      )}

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>
          <Mail size={12} />
          <strong>{content?.total_emails || 0}</strong> emails
        </div>
        {urgentEmails.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--danger, #ef4444)' }}>
            <AlertTriangle size={12} />
            <strong>{urgentEmails.length}</strong> urgent
          </div>
        )}
        {suggestions.pending > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--accent, #6366f1)' }}>
            <MessageSquare size={12} />
            <strong>{suggestions.pending}</strong> pending
          </div>
        )}
      </div>

      {Object.keys(categories).length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
          {Object.entries(categories).map(([cat, count]) => (
            <span key={cat} className="email-badge" style={{ fontSize: 11 }}>
              {cat} ({count})
            </span>
          ))}
        </div>
      )}

      {urgentEmails.length > 0 && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.05)',
          border: '1px solid rgba(239, 68, 68, 0.12)',
          borderRadius: 10,
          padding: '8px 12px',
          marginBottom: 10,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--danger, #ef4444)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
            Needs Attention
          </div>
          {urgentEmails.slice(0, 3).map((email) => (
            <div key={email.id} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>
              <strong>{email.sender?.split('<')[0]?.trim()}</strong>: {email.subject}
            </div>
          ))}
          {urgentEmails.length > 3 && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              +{urgentEmails.length - 3} more
            </div>
          )}
        </div>
      )}

      {suggestions.total > 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
          Suggestions: {suggestions.accepted} accepted, {suggestions.rejected} rejected, {suggestions.pending} pending
        </div>
      )}

      <div className="card-actions">
        <button className="btn btn-secondary" onClick={handleRefresh} disabled={refreshing} style={{ fontSize: 12 }}>
          {refreshing ? (
            <><Loader2 size={12} style={{ display: 'inline', marginRight: 4, animation: 'spin 1s linear infinite' }} /> Refreshing...</>
          ) : (
            <><RefreshCw size={12} style={{ display: 'inline', marginRight: 4 }} /> Refresh Digest</>
          )}
        </button>
      </div>
    </div>
  )
}
