from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from core.config import settings
from core.logging import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential
import json

logger = get_logger(__name__)


class LLMRouter:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            organization=settings.OPENAI_ORG_ID if settings.OPENAI_ORG_ID else None
        )
        self.classification_model = settings.CLASSIFICATION_MODEL
        self.drafting_model = settings.DRAFTING_MODEL
        self.summarization_model = settings.SUMMARIZATION_MODEL

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def classify_email(self, email_content: str, subject: str, sender: str) -> Dict[str, Any]:
        prompt = f"""Analyze this email and provide a structured classification.

Subject: {subject}
From: {sender}
Content: {email_content}

Return JSON with:
- urgent: boolean (time-sensitive or critical)
- needs_response: boolean (requires a reply)
- category: string (e.g., "work", "personal", "promotional", "informational", "support")
- confidence: float (0.0 to 1.0)
- reasoning: string (brief explanation)
"""

        response = await self.client.chat.completions.create(
            model=self.classification_model,
            messages=[
                {"role": "system", "content": "You are an email classification system. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        logger.info("email_classified", category=result.get("category"), confidence=result.get("confidence"))

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def draft_reply(
        self,
        email_content: str,
        thread_context: List[str],
        similar_emails: List[str],
        style_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        context_str = "\n\n---\n\n".join(thread_context) if thread_context else "No prior context"
        similar_str = "\n\n---\n\n".join(similar_emails[:3]) if similar_emails else "No similar examples"

        style_instructions = self._build_style_instructions(style_profile)

        prompt = f"""Draft a reply to this email based on the context and user's writing style.

CURRENT EMAIL:
{email_content}

THREAD CONTEXT:
{context_str}

SIMILAR PAST EMAILS:
{similar_str}

STYLE GUIDELINES:
{style_instructions}

RULES:
- Do not hallucinate facts or commitments
- Use only information provided in the context
- Match the user's style and tone
- Keep it concise and professional
- If you cannot draft a complete reply with confidence, say so

Return JSON with:
- draft: string (the proposed reply)
- confidence: float (0.0 to 1.0)
- reasoning: string (why this approach)
- requires_info: array of strings (what information is missing, if any)
"""

        response = await self.client.chat.completions.create(
            model=self.drafting_model,
            messages=[
                {"role": "system", "content": "You are an email reply assistant. Always respond with valid JSON. Never hallucinate commitments or facts."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        logger.info("reply_drafted", confidence=result.get("confidence"))

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def verify_reply(self, original_email: str, drafted_reply: str) -> Dict[str, Any]:
        prompt = f"""Verify this drafted email reply for safety and accuracy.

ORIGINAL EMAIL:
{original_email}

DRAFTED REPLY:
{drafted_reply}

Check for:
- Hallucinated facts or commitments
- Financial commitments
- Legal commitments
- Inappropriate tone
- Missing critical information

Return JSON with:
- safe: boolean
- concerns: array of strings (list any issues found)
- risk_level: string ("low", "medium", "high")
"""

        response = await self.client.chat.completions.create(
            model=self.classification_model,
            messages=[
                {"role": "system", "content": "You are a safety verification system. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        logger.info("reply_verified", safe=result.get("safe"), risk_level=result.get("risk_level"))

        return result

    async def generate_embedding(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def _build_style_instructions(self, style_profile: Dict[str, Any]) -> str:
        if not style_profile:
            return "Use a professional, neutral tone."

        instructions = []

        if tone := style_profile.get("tone"):
            instructions.append(f"Tone: {tone}")

        if formality := style_profile.get("formality"):
            instructions.append(f"Formality: {formality}")

        if avg_length := style_profile.get("avg_length"):
            instructions.append(f"Target length: ~{avg_length} words")

        if greetings := style_profile.get("greeting_patterns"):
            instructions.append(f"Typical greetings: {', '.join(greetings[:3])}")

        if signoffs := style_profile.get("signoff_patterns"):
            instructions.append(f"Typical signoffs: {', '.join(signoffs[:3])}")

        if style_profile.get("emoji_usage", 0) > 0.2:
            instructions.append("User occasionally uses emojis")

        return "\n".join(instructions) if instructions else "Use a professional, neutral tone."


llm_router = LLMRouter()
