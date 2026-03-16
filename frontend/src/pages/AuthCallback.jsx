import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState(null)

  useEffect(() => {
    const handleCallback = async () => {
      const token = searchParams.get('token')
      const userId = searchParams.get('user_id')
      const email = searchParams.get('email')

      if (token && email) {
        login(token, { id: userId, email })

        try {
          const userInfo = await api.getMe()
          const onboarded = userInfo?.onboarding_completed || false
          login(token, { id: userId, email, onboarding_completed: onboarded })
          navigate(onboarded ? '/' : '/onboarding')
        } catch {
          navigate('/onboarding')
        }
      } else {
        setError('Authentication failed. No token received.')
      }
    }

    handleCallback()
  }, [])

  if (error) {
    return (
      <div className="app-container">
        <div className="login-container">
          <h1>Auth Error</h1>
          <p style={{ color: 'rgba(255,255,255,0.6)' }}>{error}</p>
          <button className="login-btn" onClick={() => navigate('/login')} style={{ marginTop: 20 }}>
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <div className="loading-container">
        <div className="spinner" />
        <div className="loading-text">Signing you in...</div>
      </div>
    </div>
  )
}
