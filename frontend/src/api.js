const API_BASE = '';

function getToken() {
  return localStorage.getItem('echo_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('echo_token');
    localStorage.removeItem('echo_user');
    window.location.href = '/login';
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  return res.json();
}

export const api = {
  // Auth
  googleLogin: () => request('/auth/google/login'),

  // User
  getMe: () => request('/users/me'),
  completeOnboarding: () => request('/users/me/onboarding/complete', { method: 'POST' }),

  // Emails
  fetchEmails: (maxResults = 20) =>
    request(`/emails/fetch?max_results=${maxResults}`, { method: 'POST' }),
  listEmails: (skip = 0, limit = 50) =>
    request(`/emails/?skip=${skip}&limit=${limit}`),
  getEmail: (id) => request(`/emails/${id}`),

  // Suggestions
  listSuggestions: (status = 'pending', limit = 20) =>
    request(`/suggestions/?status_filter=${status}&limit=${limit}`),
  submitFeedback: (id, feedback) =>
    request(`/suggestions/${id}/feedback`, {
      method: 'POST',
      body: JSON.stringify(feedback),
    }),

  // Digests
  getLatestDigest: () => request('/digests/latest'),
  listDigests: (limit = 7) => request(`/digests/?limit=${limit}`),
  generateDigest: () => request('/digests/generate', { method: 'POST' }),

  // Calendar
  listEvents: (daysAhead = 7) =>
    request(`/calendar/events?days_ahead=${daysAhead}`),
  listManagedEvents: (limit = 20) =>
    request(`/calendar/events/managed?limit=${limit}`),
  processEmailForCalendar: (emailId) =>
    request(`/calendar/process-email/${emailId}`, { method: 'POST' }),

  // Chat
  sendChatMessage: (message) =>
    request('/chat/send', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  sendDraftEmail: (draft) =>
    request('/chat/send-draft', {
      method: 'POST',
      body: JSON.stringify(draft),
    }),

  // Notifications
  listNotifications: (unreadOnly = false, limit = 30) =>
    request(`/notifications/?unread_only=${unreadOnly}&limit=${limit}`),
  getUnreadCount: () => request('/notifications/unread-count'),
  markNotificationRead: (id) =>
    request(`/notifications/${id}/read`, { method: 'PATCH' }),
  markAllNotificationsRead: () =>
    request('/notifications/read-all', { method: 'PATCH' }),
  executeNotificationAction: (id, action) =>
    request(`/notifications/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    }),

  // Tasks
  listTasks: (statusFilter, sourceFilter, limit = 50) => {
    const params = new URLSearchParams()
    if (statusFilter) params.set('status_filter', statusFilter)
    if (sourceFilter) params.set('source_filter', sourceFilter)
    params.set('limit', limit)
    return request(`/tasks/?${params}`)
  },
  createTask: (data) =>
    request('/tasks/', { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (id, updates) =>
    request(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(updates) }),
  deleteTask: (id) =>
    request(`/tasks/${id}`, { method: 'DELETE' }),
};
