# ECHO — Smart Email Assistant
## Complete Application Flow

---

### Screen 1: Login

The entry point to ECHO. The user is greeted with the ECHO branding and a "Sign in with Google" button. This initiates Google OAuth, granting ECHO access to the user's Gmail and Calendar.

**[Screenshot: Login page with Google sign-in button]**

---

### Screen 2: Onboarding

First-time users are walked through a 6-step introduction explaining what ECHO does:

- Smart email classification
- AI-drafted replies tailored to their tone
- Calendar awareness and conflict detection
- Full user control over every action

The user can skip or step through. On the final step, ECHO fetches and classifies the user's recent emails automatically.

**[Screenshot: Onboarding walkthrough — any step]**

---

### Screen 3: Dashboard — Messages Tab

The main hub. At the top, a Summary Card shows how many emails have been screened, how many need a response, and how many are urgent. Below it, the next upcoming meeting is displayed. The rest of the screen lists email cards, each showing the sender, subject, a body preview, and urgency badges.

**[Screenshot: Dashboard showing Summary Card, Meeting Card, and Email Cards]**

---

### Screen 4: AI-Suggested Reply on an Email

When ECHO generates a reply suggestion for an email, it appears as a highlighted box inside the email card. The user has two options:

- "Accept & Send" — sends the draft as-is through Gmail
- "Write My Own" — opens an editable text area so the user can type a custom reply. ECHO learns from the correction for future suggestions.

**[Screenshot: An email card with an AI suggestion box and the Accept / Write My Own buttons]**

---

### Screen 5: Chat — Text Reply

The chat bar at the bottom lets the user ask ECHO anything about their inbox. For general questions like "summarize my unread emails" or "what's on my calendar today", ECHO responds with a plain text answer displayed above the input.

**[Screenshot: Chat input with a text reply from ECHO]**

---

### Screen 6: Chat — Email Drafting

When the user asks ECHO to draft an email (e.g., "draft an email to alishba asking about the sprint"), ECHO returns a styled email card with To, Subject, and Body fields pre-filled. The user can:

- Click "Send" to send the email via Gmail immediately
- Click "Alter" to make the fields editable and modify anything before sending
- Click "X" to dismiss the draft

If the recipient is a name or project reference rather than an email address, ECHO resolves it automatically using the user's contacts or by querying HERA for project team members.

**[Screenshot: Email draft card in the chat area with To / Subject / Body and Send / Alter buttons]**

---

### Screen 7: Chat — Calendar Event Creation

When the user says something like "set a team standup for 10pm", ECHO creates a Google Calendar event directly and shows a confirmation card with the event summary, time, and invited attendees. If there is a scheduling conflict, ECHO shows a warning with the conflicting event details. Project team members are automatically invited by looking them up from HERA.

**[Screenshot: Calendar event created confirmation card in chat]**

---

### Screen 8: Dashboard — Tasks Tab

Switching to the Tasks tab shows active and completed tasks. Tasks can come from HERA (assigned by a manager), from emails (extracted action items), or be created manually. Each task card shows the title, status, priority, deadline, source, and project name. The user can transition tasks through statuses: Pending, In Progress, and Completed.

**[Screenshot: Tasks tab showing task cards with status badges and deadline indicators]**

---

### Screen 9: Daily Digest

ECHO generates a daily digest summarizing the user's email activity — total emails screened, urgent items, category breakdown (Work, Personal, etc.), top urgent messages, and suggestion acceptance stats. The user can manually refresh the digest at any time.

**[Screenshot: Daily Digest card with email stats and category breakdown]**

---

### Screen 10: Notification Panel

Clicking the bell icon in the top-right opens the notification panel. Notifications come from both ECHO (deadline reminders, email alerts) and HERA (new task assignments). Each notification shows a title, message, source tag, and timestamp. Actionable notifications have Confirm and Dismiss buttons. A "Mark all as read" option clears the unread badge.

**[Screenshot: Notification panel open, showing a mix of ECHO and HERA notifications]**

---

### Cross-Module Connections

- When a manager confirms task assignments in HERA, assigned employees receive notifications in ECHO
- When ECHO drafts an email to a project team, it queries HERA to resolve team member emails
- Calendar events created from ECHO chat automatically invite HERA project team members
- Employee productivity data (suggestion acceptance rates, notification engagement) flows from ECHO to ARGUS for scoring
