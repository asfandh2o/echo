# Google OAuth Setup for ECHO

Complete guide to connect Gmail to your ECHO system.

## Prerequisites
- Google Account (any Gmail)
- 10 minutes
- Credit card for verification (won't be charged)

---

## Step 1: Create Google Cloud Project

### 1.1 Go to Google Cloud Console
**URL**: https://console.cloud.google.com/

### 1.2 Create New Project
1. Click **"Select a project"** at top
2. Click **"New Project"**
3. Enter project name: `ECHO-AI-Assistant`
4. Click **"Create"**
5. Wait 30 seconds for project creation

### 1.3 Select Your Project
- Make sure "ECHO-AI-Assistant" is selected in the dropdown

---

## Step 2: Enable Required APIs

### 2.1 Enable Gmail API
1. Go to: https://console.cloud.google.com/apis/library
2. Search for: **"Gmail API"**
3. Click on **Gmail API**
4. Click **"Enable"**
5. Wait for activation

### 2.2 Enable Google Calendar API (Optional)
1. Search for: **"Google Calendar API"**
2. Click **"Enable"**

### 2.3 Enable Google Drive API (Optional)
1. Search for: **"Google Drive API"**
2. Click **"Enable"**

---

## Step 3: Configure OAuth Consent Screen

### 3.1 Go to OAuth Consent Screen
**URL**: https://console.cloud.google.com/apis/credentials/consent

### 3.2 Choose User Type
- Select: **"External"**
- Click **"Create"**

### 3.3 Fill Out App Information

**App Information**:
- **App name**: `ECHO AI Assistant`
- **User support email**: Your Gmail address
- **App logo**: (Skip for now)

**App domain** (all optional for testing):
- Skip for now

**Developer contact information**:
- **Email**: Your Gmail address

Click **"Save and Continue"**

### 3.4 Scopes
Click **"Add or Remove Scopes"**

**Add these scopes**:
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/calendar.readonly (optional)
```

**To add manually**:
1. Scroll to bottom
2. Click "Manually add scopes"
3. Paste each scope above
4. Click "Add to Table"

Click **"Save and Continue"**

### 3.5 Test Users
Click **"Add Users"**

**Add your Gmail address** (the one you'll test with)

Click **"Save and Continue"**

### 3.6 Summary
Review and click **"Back to Dashboard"**

---

## Step 4: Create OAuth Credentials

### 4.1 Go to Credentials
**URL**: https://console.cloud.google.com/apis/credentials

### 4.2 Create OAuth Client ID
1. Click **"+ Create Credentials"**
2. Select **"OAuth client ID"**

### 4.3 Configure OAuth Client

**Application type**:
- Select: **"Web application"**

**Name**:
- Enter: `ECHO Web Client`

**Authorized JavaScript origins**:
- Click **"+ Add URI"**
- Add: `http://localhost:8000`

**Authorized redirect URIs**:
- Click **"+ Add URI"**
- Add: `http://localhost:8000/auth/google/callback`

⚠️ **CRITICAL**: The redirect URI must be EXACTLY:
```
http://localhost:8000/auth/google/callback
```
No trailing slash, no typos!

Click **"Create"**

### 4.4 Copy Credentials

A popup will show your credentials:

**Copy these** (you'll need them):
```
Client ID: something.apps.googleusercontent.com
Client Secret: GOCSPX-xxxxxxxxxxxxx
```

Click **"Download JSON"** (optional, for backup)

---

## Step 5: Add Credentials to ECHO

### 5.1 Open .env File
```bash
cd C:\Users\Shaggy\echo
notepad .env
```

### 5.2 Update OAuth Settings

Find these lines:
```bash
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

Replace with YOUR credentials:
```bash
GOOGLE_CLIENT_ID=123456789-abc123.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-actual-secret-here
```

Save the file (Ctrl+S)

---

## Step 6: Test OAuth Flow

### 6.1 Make Sure System is Running

**If using Groq demo**:
```bash
# Already running on port 8001
curl http://localhost:8001/health
```

**If using full system**:
```bash
docker-compose up -d
curl http://localhost:8000/health
```

### 6.2 Start OAuth Flow

**Visit this URL in browser**:
```
http://localhost:8000/auth/google/login
```

(Use port 8001 if testing with Groq demo)

### 6.3 Complete Authorization

1. Click the link in the response
2. Select your Google account
3. Click **"Continue"** on the warning screen
   - (Shows warning because app not verified - this is normal for testing)
4. Check all permission boxes
5. Click **"Continue"**

### 6.4 Get Your Token

After authorization, you'll receive:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "your@gmail.com"
  }
}
```

**Save the access_token** - you'll use it for all API calls!

---

## Step 7: Test API Access

### 7.1 Export Token
```bash
export TOKEN="your-access-token-here"
```

### 7.2 Test Endpoints

**Get your user info**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/users/me
```

**List emails** (once ingestion runs):
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/emails/
```

**List suggestions**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/suggestions/
```

---

## Troubleshooting

### "redirect_uri_mismatch" Error

**Problem**: Redirect URI doesn't match

**Solution**:
- Google Console redirect URI must EXACTLY match: `http://localhost:8000/auth/google/callback`
- No https
- No trailing slash
- Correct port (8000 or 8001)

### "Access blocked: This app's request is invalid"

**Problem**: Scopes not configured

**Solution**:
- Go back to OAuth Consent Screen
- Add required scopes
- Make sure Gmail API is enabled

### "This app isn't verified"

**This is NORMAL for testing!**

Click **"Advanced"** → **"Go to ECHO (unsafe)"**

You can verify the app later when ready for production.

### Can't Find OAuth Settings

1. Make sure project is selected (top bar)
2. Go to: APIs & Services → Credentials
3. If no OAuth client exists, create one

### Rate Limits

**Free tier limits**:
- 250 quota units per user per second
- 1 billion quota units per day

For ECHO, this is MORE than enough.

---

## Security Notes

### For Testing
- ✅ OAuth 2.0 is secure
- ✅ Tokens encrypted at rest in ECHO
- ✅ User type "External" is fine for testing

### For Production
1. Verify your app (submit for review)
2. Add privacy policy URL
3. Use HTTPS (not HTTP)
4. Restrict scopes to minimum needed
5. Set up monitoring

---

## What Happens After OAuth

Once configured:

1. **Emails fetched** every 5 minutes automatically
2. **Classified** with Groq AI
3. **Suggestions generated** with Groq AI
4. **Available via API** for review

### Manual Email Fetch

Don't want to wait 5 minutes? Trigger manually:

```bash
docker-compose exec worker celery -A workers.celery_app call \
  workers.tasks.fetch_emails_for_user \
  --args='["your-user-id"]'
```

---

## Summary Checklist

- [ ] Google Cloud project created
- [ ] Gmail API enabled
- [ ] OAuth consent screen configured
- [ ] Test user added (your Gmail)
- [ ] OAuth client ID created
- [ ] Redirect URI set correctly
- [ ] Credentials copied
- [ ] Added to `.env` file
- [ ] OAuth flow tested
- [ ] JWT token received
- [ ] First API call successful

---

## Quick Reference

**Google Cloud Console**: https://console.cloud.google.com/

**Required Scopes**:
```
gmail.readonly
gmail.send
gmail.modify
userinfo.email
```

**Redirect URI**:
```
http://localhost:8000/auth/google/callback
```

**OAuth Flow**:
```
1. GET /auth/google/login
2. Visit authorization_url
3. Complete Google auth
4. GET /auth/google/callback?code=...
5. Receive JWT token
6. Use token in Authorization header
```

You're ready to connect Gmail! 🚀
