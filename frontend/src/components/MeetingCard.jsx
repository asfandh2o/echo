import { Clock, MapPin } from 'lucide-react'

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function parseEventTime(isoStr) {
  // Parse time directly from ISO string to match Google Calendar exactly
  // (avoids browser timezone conversion)
  const match = isoStr.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (!match) return { dateStr: isoStr, timeStr: '' }
  const [, year, month, day, hour, minute] = match
  const dt = new Date(+year, +month - 1, +day)
  const dayName = DAYS[dt.getDay()]
  const monthName = MONTHS[+month - 1]
  const h12 = +hour % 12 || 12
  const ampm = +hour >= 12 ? 'PM' : 'AM'
  return {
    dateStr: `${dayName} ${monthName} ${+day}`,
    timeStr: `${h12}:${minute} ${ampm}`,
  }
}

export default function MeetingCard({ event }) {
  const { dateStr, timeStr } = parseEventTime(event.start)

  return (
    <div className="card">
      <div className="meeting-time">
        <Clock size={13} />
        <span>{dateStr} at {timeStr}</span>
      </div>
      <h3>{event.summary || 'Untitled Meeting'}</h3>
      {event.location && (
        <p style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
          <MapPin size={12} /> {event.location}
        </p>
      )}
      {event.attendees && event.attendees.length > 0 && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          {event.attendees.length} attendee{event.attendees.length !== 1 ? 's' : ''}
        </p>
      )}
      {event.description && (
        <p style={{ fontSize: 12, marginTop: 6 }}>{event.description.slice(0, 120)}</p>
      )}
    </div>
  )
}
