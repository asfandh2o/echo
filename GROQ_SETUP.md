# Groq Setup Guide

## Why Groq?

- ✅ **FREE tier** with generous limits
- ✅ **Extremely fast** inference (10x faster than OpenAI)
- ✅ **High quality** Llama 3.3 70B model
- ✅ Easy to switch to OpenAI later

## Step 1: Get Free Groq API Key

1. **Go to**: https://console.groq.com/
2. **Sign up** with Google or Email (takes 30 seconds)
3. **Navigate to**: API Keys section
4. **Create** new API key
5. **Copy** the key (starts with `gsk_...`)

## Step 2: Configure ECHO

Edit `.env` file:

```bash
# Set provider to Groq
LLM_PROVIDER=groq

# Add your Groq API key
GROQ_API_KEY=gsk_your_actual_key_here

# Use Groq models
CLASSIFICATION_MODEL=llama-3.3-70b-versatile
DRAFTING_MODEL=llama-3.3-70b-versatile
SUMMARIZATION_MODEL=llama-3.3-70b-versatile
```

## Step 3: Test It

```bash
# Start the system with Docker
docker-compose up -d
docker-compose exec api alembic upgrade head

# Check logs to confirm Groq is being used
docker-compose logs api | grep "llm_router_initialized"
# Should see: provider="groq"
```

## Available Groq Models

### Recommended for ECHO

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| `llama-3.3-70b-versatile` | Fast | Excellent | General purpose (RECOMMENDED) |
| `llama-3.1-70b-versatile` | Fast | Excellent | Alternative |
| `mixtral-8x7b-32768` | Fastest | Good | Cost-sensitive |

### Specialized Models

| Model | Use Case |
|-------|----------|
| `llama-3.3-70b-specdec` | Speculative decoding (faster) |
| `gemma2-9b-it` | Lightweight, faster |

## Groq Free Tier Limits

- **Requests per minute**: 30
- **Requests per day**: 14,400
- **Tokens per minute**: 20,000
- **Context length**: Up to 128k tokens

**For ECHO usage**: This is MORE than enough for personal use!

Example:
- Classify 1,000 emails/day ✅
- Draft 200 suggestions/day ✅

## Switch to OpenAI Later

When ready to use OpenAI:

1. Get OpenAI API key from: https://platform.openai.com/api-keys
2. Edit `.env`:
   ```bash
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-your-openai-key
   CLASSIFICATION_MODEL=gpt-4o-mini
   DRAFTING_MODEL=gpt-4o
   ```
3. Restart: `docker-compose restart api worker`

That's it! The system automatically switches.

## Troubleshooting

### "Invalid API Key"
- Check key starts with `gsk_`
- No spaces or quotes in `.env`
- Key hasn't expired

### "Rate limit exceeded"
- Free tier: 30 requests/minute
- Add delay between requests
- Upgrade to paid tier if needed

### "Model not found"
- Check spelling: `llama-3.3-70b-versatile`
- Use exact model names from Groq docs

## Cost Comparison

| Provider | Classification | Drafting | Monthly (Personal) |
|----------|---------------|----------|-------------------|
| **Groq** | FREE | FREE | **$0** |
| OpenAI | $0.10 | $1.00 | $5-10 |

Start with Groq for FREE, switch to OpenAI when you need it!
