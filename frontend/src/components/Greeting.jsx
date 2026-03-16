export default function Greeting({ email }) {
  const hour = new Date().getHours()
  let timeGreeting = 'Good Morning'
  if (hour >= 12 && hour < 17) timeGreeting = 'Good Afternoon'
  else if (hour >= 17) timeGreeting = 'Good Evening'

  const name = email ? email.split('@')[0] : 'there'
  const displayName = name.charAt(0).toUpperCase() + name.slice(1)

  return (
    <div className="greeting">
      <h2>{timeGreeting}, {displayName}!</h2>
    </div>
  )
}
