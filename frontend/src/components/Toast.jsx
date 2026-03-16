export default function Toast({ title, body }) {
  return (
    <div className="toast">
      <div className="toast-title">{title}</div>
      {body && <div className="toast-body">{body}</div>}
    </div>
  )
}
