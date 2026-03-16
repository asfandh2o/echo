import { useState } from 'react'
import { api } from '../api'

export default function Login() {
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    setLoading(true)
    try {
      const data = await api.googleLogin()
      window.location.href = data.authorization_url
    } catch (err) {
      console.error('Login failed:', err)
      setLoading(false)
    }
  }

  return (
    <div className="app-container">
      <div className="login-container">
        <div className="login-logo">ECHO</div>
        <h1>Welcome to ECHO</h1>
        <p>Your AI-powered email assistant</p>
        <button className="login-btn" onClick={handleLogin} disabled={loading}>
          {loading ? 'Connecting...' : 'Sign in with Google'}
        </button>
      </div>
    </div>
  )
}
