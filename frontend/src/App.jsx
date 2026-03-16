import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Onboarding from './pages/Onboarding'
import AuthCallback from './pages/AuthCallback'
import './App.css'

function App() {
  const { isAuthenticated, user } = useAuth()
  const onboarded = user?.onboarding_completed

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/onboarding"
        element={
          !isAuthenticated ? <Navigate to="/login" /> :
          onboarded ? <Navigate to="/" /> :
          <Onboarding />
        }
      />
      <Route
        path="/"
        element={
          !isAuthenticated ? <Navigate to="/login" /> :
          !onboarded ? <Navigate to="/onboarding" /> :
          <Dashboard />
        }
      />
    </Routes>
  )
}

export default App
