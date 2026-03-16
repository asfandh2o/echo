import { RefreshCw, Loader2 } from 'lucide-react'

export default function SummaryCard({
  totalEmails,
  urgentCount,
  pendingSuggestions,
  needsResponse,
  onRefresh,
  fetching,
}) {
  const reviewCount = urgentCount + pendingSuggestions

  return (
    <div className="card">
      <h3>
        {reviewCount > 0
          ? `You have ${reviewCount} thing${reviewCount !== 1 ? 's' : ''} to review.`
          : 'All caught up!'}
      </h3>
      <div className="summary-stats">
        {totalEmails > 0 && (
          <>
            I screened {totalEmails} emails.
            {needsResponse > 0 && ` ${needsResponse} need${needsResponse !== 1 ? '' : 's'} a response.`}
            {urgentCount > 0 && ` ${urgentCount} urgent.`}
            {pendingSuggestions > 0 && ` ${pendingSuggestions} draft${pendingSuggestions !== 1 ? 's' : ''} ready for review.`}
          </>
        )}
        {totalEmails === 0 && 'No emails fetched yet.'}
      </div>
      <div className="card-actions">
        <button className="btn btn-primary" onClick={onRefresh} disabled={fetching}>
          {fetching ? (
            <><Loader2 size={14} style={{ display: 'inline', marginRight: 6, animation: 'spin 1s linear infinite' }} /> Fetching...</>
          ) : (
            <><RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} /> Refresh Emails</>
          )}
        </button>
      </div>
    </div>
  )
}
