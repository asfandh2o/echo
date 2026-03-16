import { useState } from 'react'
import { FileText, AlertTriangle, Mail, MessageSquare, RefreshCw, Loader2, X, Clock, CheckCircle2, XCircle, ChevronRight } from 'lucide-react'
import { api } from '../api'

export default function DigestNotification({ digest, onRefresh, visible, onDismiss }) {
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

  if (!visible) return null

  // No digest yet
  if (!digest) {
    return (
      <div className="digest-overlay" onClick={onDismiss}>
        <div className="digest-panel digest-panel-in" onClick={e => e.stopPropagation()}>
          <div className="digest-panel-header">
            <div className="digest-panel-title">
              <FileText size={16} />
              Daily Digest
            </div>
            <button className="digest-close-btn" onClick={onDismiss}>
              <X size={16} />
            </button>
          </div>
          <div className="digest-panel-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <FileText size={36} style={{ color: 'rgba(255,255,255,0.15)', marginBottom: 16 }} />
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px' }}>
                No digest available yet.
              </p>
              <button className="btn btn-primary" onClick={handleRefresh} disabled={refreshing} style={{ fontSize: 12 }}>
                {refreshing ? (
                  <><Loader2 size={13} className="spin" style={{ display: 'inline', marginRight: 6 }} /> Generating...</>
                ) : (
                  'Generate Digest'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const { content, llm_summary } = digest
  const categories = content?.category_breakdown || {}
  const urgentEmails = content?.urgent_emails || []
  const suggestions = content?.suggestions_summary || {}
  const digestDate = new Date(digest.digest_date + 'T00:00:00')
  const dateStr = digestDate.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })

  return (
    <div className="digest-overlay" onClick={onDismiss}>
      <div className="digest-panel digest-panel-in" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="digest-panel-header">
          <div className="digest-panel-title">
            <FileText size={16} />
            Daily Digest
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="digest-date-badge">{dateStr}</span>
            <button className="digest-close-btn" onClick={onDismiss}>
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="digest-panel-body">
          {/* Summary */}
          {llm_summary && (
            <p className="digest-summary">{llm_summary}</p>
          )}

          {/* Stat Cards */}
          <div className="digest-stat-grid">
            <div className="digest-stat-card">
              <Mail size={16} className="digest-stat-icon" />
              <div className="digest-stat-value">{content?.total_emails || 0}</div>
              <div className="digest-stat-label">Emails</div>
            </div>
            <div className="digest-stat-card digest-stat-card-urgent">
              <AlertTriangle size={16} className="digest-stat-icon" />
              <div className="digest-stat-value">{urgentEmails.length}</div>
              <div className="digest-stat-label">Urgent</div>
            </div>
            <div className="digest-stat-card digest-stat-card-accent">
              <Clock size={16} className="digest-stat-icon" />
              <div className="digest-stat-value">{suggestions.pending || 0}</div>
              <div className="digest-stat-label">Pending</div>
            </div>
          </div>

          {/* Categories */}
          {Object.keys(categories).length > 0 && (
            <div className="digest-section">
              <div className="digest-section-label">Categories</div>
              <div className="digest-categories">
                {Object.entries(categories).map(([cat, count]) => (
                  <span key={cat} className="digest-cat-badge">
                    {cat} <span className="digest-cat-count">{count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Needs Attention */}
          {urgentEmails.length > 0 && (
            <div className="digest-section">
              <div className="digest-section-label digest-section-label-urgent">
                <AlertTriangle size={12} />
                Needs Attention
              </div>
              <div className="digest-urgent-list">
                {urgentEmails.slice(0, 4).map((email) => {
                  const senderName = email.sender?.split('<')[0]?.trim() || 'Unknown'
                  return (
                    <div key={email.id} className="digest-urgent-row">
                      <div className="digest-urgent-sender">{senderName}</div>
                      <div className="digest-urgent-subject">{email.subject}</div>
                    </div>
                  )
                })}
                {urgentEmails.length > 4 && (
                  <div className="digest-urgent-more">
                    +{urgentEmails.length - 4} more items
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Suggestions */}
          {suggestions.total > 0 && (
            <div className="digest-section">
              <div className="digest-section-label">Suggestions</div>
              <div className="digest-suggestion-row">
                {suggestions.accepted > 0 && (
                  <div className="digest-suggestion-pill digest-suggestion-accepted">
                    <CheckCircle2 size={12} />
                    {suggestions.accepted} accepted
                  </div>
                )}
                {suggestions.rejected > 0 && (
                  <div className="digest-suggestion-pill digest-suggestion-rejected">
                    <XCircle size={12} />
                    {suggestions.rejected} rejected
                  </div>
                )}
                {suggestions.pending > 0 && (
                  <div className="digest-suggestion-pill digest-suggestion-pending">
                    <Clock size={12} />
                    {suggestions.pending} pending
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Refresh */}
          <button className="digest-refresh-btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? (
              <><Loader2 size={13} className="spin" /> Refreshing...</>
            ) : (
              <><RefreshCw size={13} /> Refresh Digest</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
