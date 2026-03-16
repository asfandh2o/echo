import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('echo_user');
    return stored ? JSON.parse(stored) : null;
  });

  const [token, setToken] = useState(() => localStorage.getItem('echo_token'));

  const login = (accessToken, userData) => {
    localStorage.setItem('echo_token', accessToken);
    localStorage.setItem('echo_user', JSON.stringify(userData));
    setToken(accessToken);
    setUser(userData);
  };

  const completeOnboarding = () => {
    const updated = { ...user, onboarding_completed: true };
    localStorage.setItem('echo_user', JSON.stringify(updated));
    setUser(updated);
  };

  const logout = () => {
    localStorage.removeItem('echo_token');
    localStorage.removeItem('echo_user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, completeOnboarding, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
