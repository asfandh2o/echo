"""
Multi-Provider LLM Router supporting both Groq and OpenAI
Switch between providers by changing LLM_PROVIDER in .env
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import AsyncOpenAI
from groq import AsyncGroq
from core.config import settings
from core.logging import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import re

logger = get_logger(__name__)


class MultiProviderLLMRouter:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()

        if self.provider == "groq":
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            logger.info("llm_router_initialized", provider="groq")
        elif self.provider == "openai":
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                organization=settings.OPENAI_ORG_ID if settings.OPENAI_ORG_ID else None
            )
            logger.info("llm_router_initialized", provider="openai")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

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
            response_format={"type": "json_object"} if self.provider == "openai" else None,
            temperature=0.3,
        )

        content = response.choices[0].message.content

        # Parse JSON (Groq might need extra cleaning)
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)

        logger.info(
            "email_classified",
            provider=self.provider,
            category=result.get("category"),
            confidence=result.get("confidence")
        )

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def draft_reply(
        self,
        email_content: str,
        thread_context: List[str],
        similar_emails: List[str],
        style_profile: Dict[str, Any],
        contact_context: Optional[Dict[str, Any]] = None,
        document_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        context_str = "\n\n---\n\n".join(thread_context) if thread_context else "No prior context"
        similar_str = "\n\n---\n\n".join(similar_emails[:3]) if similar_emails else "No similar examples"

        style_instructions = self._build_style_instructions(style_profile)
        contact_str = self._build_contact_context(contact_context) if contact_context else "No prior contact information."

        # Build document context string from Google Drive search results
        doc_str = "No relevant company documents found."
        if document_context:
            doc_parts = []
            for doc in document_context:
                doc_parts.append(
                    f'[Source: "{doc["document_name"]}" (modified {doc["modified_at"]})]\n{doc["content"]}'
                )
            doc_str = "\n\n---\n\n".join(doc_parts)

        prompt = f"""Draft a reply to this email based on the context, sender info, company documents, and user's writing style.

CURRENT EMAIL:
{email_content}

THREAD CONTEXT:
{context_str}

SIMILAR PAST EMAILS:
{similar_str}

SENDER CONTEXT:
{contact_str}

COMPANY DOCUMENTS (from Google Drive):
{doc_str}

STYLE GUIDELINES:
{style_instructions}

RULES:
- Do not hallucinate facts or commitments
- Use only information provided in the context and company documents
- When referencing information from company documents, cite the source document name
- ONLY use facts explicitly stated in the documents — never infer or assume document content
- If the documents contain relevant project details, use them to make the reply more informed
- Match the user's style and tone
- Use the sender context to personalize the reply (reference shared topics, use appropriate formality for the relationship)
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
            response_format={"type": "json_object"} if self.provider == "openai" else None,
            temperature=0.7,
        )

        content = response.choices[0].message.content

        # Parse JSON (Groq might need extra cleaning)
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)

        logger.info(
            "reply_drafted",
            provider=self.provider,
            confidence=result.get("confidence")
        )

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
            response_format={"type": "json_object"} if self.provider == "openai" else None,
            temperature=0.1,
        )

        content = response.choices[0].message.content

        # Parse JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)

        logger.info(
            "reply_verified",
            provider=self.provider,
            safe=result.get("safe"),
            risk_level=result.get("risk_level")
        )

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def extract_meeting_details(self, email_content: str, subject: str, sender: str) -> Dict[str, Any]:
        from datetime import date as date_cls, timedelta as td
        today = date_cls.today()
        # Build a reference calendar for the next 7 days so the LLM can resolve relative dates accurately
        day_map = []
        for i in range(7):
            d = today + td(days=i)
            label = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime('%A'))
            day_map.append(f"  {label} = {d.isoformat()} ({d.strftime('%A')})")
        day_reference = "\n".join(day_map)

        prompt = f"""Analyze this email and determine if it contains a meeting request, scheduling, or rescheduling intent.

Today is {today.isoformat()} ({today.strftime('%A')}). Here are the next 7 days for reference:
{day_reference}

IMPORTANT: When the email says a day name like "Thursday", map it to the EXACT date from the list above.

Subject: {subject}
From: {sender}
Content: {email_content}

Return JSON with:
- has_meeting: boolean (true if email involves scheduling/rescheduling a meeting)
- action: string or null ("create", "reschedule", "cancel", or null if no meeting)
- title: string or null (meeting title/subject)
- date: string or null (ISO date like "2026-02-19" — MUST resolve relative days to the exact date from the calendar above)
- time: string or null (24h time like "15:00")
- duration_minutes: integer or null (estimated duration, default 60)
- attendees: array of strings (email addresses mentioned)
- location: string or null (meeting location or video link)
- notes: string or null (any additional context)
- original_event_reference: string or null (reference to existing event if rescheduling)
"""

        response = await self.client.chat.completions.create(
            model=self.classification_model,
            messages=[
                {"role": "system", "content": "You are a meeting extraction system. Analyze emails for scheduling intent. Always respond with valid JSON only, no extra text."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content

        result = self._parse_json_response(content)

        logger.info(
            "meeting_details_extracted",
            provider=self.provider,
            has_meeting=result.get("has_meeting"),
            action=result.get("action")
        )

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def draft_calendar_aware_reply(
        self,
        email_content: str,
        subject: str,
        sender: str,
        calendar_context: Dict[str, Any],
        style_profile: Dict[str, Any] = None,
        contact_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        style_instructions = self._build_style_instructions(style_profile or {})
        contact_str = self._build_contact_context(contact_context) if contact_context else ""

        conflict_info = ""
        if calendar_context.get("already_scheduled"):
            conflict_info = "This meeting is ALREADY ON the user's calendar. The user has already accepted/scheduled this meeting. Confirm attendance — do NOT decline or suggest alternatives."
        elif calendar_context.get("has_conflict"):
            busy_events = calendar_context.get("conflicting_events", [])
            busy_descriptions = []
            for evt in busy_events:
                busy_descriptions.append(
                    f"- {evt.get('summary', 'Busy')} ({evt.get('start')} to {evt.get('end')})"
                )
            conflict_info = f"""The user HAS A CONFLICT at the proposed time with a DIFFERENT event.
Busy during:
{chr(10).join(busy_descriptions)}
"""
            free_slots = calendar_context.get("free_slots", [])
            if free_slots:
                slot_descriptions = [
                    f"- {slot['start']} to {slot['end']}" for slot in free_slots
                ]
                conflict_info += f"""
The user IS FREE during these alternative times:
{chr(10).join(slot_descriptions)}
"""
        else:
            conflict_info = "The user is FREE at the proposed time. The meeting has been added to their calendar."

        proposed = calendar_context.get("proposed_meeting", {})
        proposed_info = ""
        if proposed:
            proposed_info = f"""Proposed meeting:
- Title: {proposed.get('title', 'Meeting')}
- Date: {proposed.get('date', 'Unknown')}
- Time: {proposed.get('time', 'Unknown')}
- Duration: {proposed.get('duration_minutes', 60)} minutes"""

        sender_section = f"\nSENDER CONTEXT:\n{contact_str}\n" if contact_str else ""

        prompt = f"""Draft a reply to this email considering the user's calendar availability.

EMAIL:
Subject: {subject}
From: {sender}
Content: {email_content}

{proposed_info}

CALENDAR STATUS:
{conflict_info}
{sender_section}
STYLE GUIDELINES:
{style_instructions}

RULES:
- If the meeting is ALREADY SCHEDULED on the calendar: confirm attendance (e.g. "Looking forward to it", "See you then")
- If there is a CONFLICT with a DIFFERENT event: politely decline the proposed time, mention you are unavailable, and suggest alternative free slots if available
- If there is NO conflict: confirm the meeting time
- Do NOT reveal specific details of what the conflicting event is (just say you have a prior commitment)
- Match the user's tone and style
- Use sender context to personalize the reply when available
- Keep it concise and professional
- Do not hallucinate facts

Return JSON with:
- draft: string (the proposed reply)
- confidence: float (0.0 to 1.0)
- reasoning: string (why this approach)
- has_conflict: boolean
- suggested_times: array of strings (alternative times suggested, if any)
"""

        response = await self.client.chat.completions.create(
            model=self.drafting_model,
            messages=[
                {"role": "system", "content": "You are a calendar-aware email reply assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content
        result = self._parse_json_response(content)

        logger.info(
            "calendar_aware_reply_drafted",
            provider=self.provider,
            has_conflict=calendar_context.get("has_conflict"),
            confidence=result.get("confidence")
        )

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_digest_summary(self, digest_content: Dict[str, Any]) -> str:
        """Generate a concise 2-4 sentence daily digest summary."""
        total = digest_content.get("total_emails", 0)
        categories = digest_content.get("category_breakdown", {})
        urgent = digest_content.get("urgent_emails", [])
        suggestions = digest_content.get("suggestions_summary", {})

        category_str = ", ".join(f"{cat}: {count}" for cat, count in categories.items()) if categories else "none classified"
        urgent_subjects = [e.get("subject", "Unknown") for e in urgent[:5]]
        urgent_str = "\n".join(f"- {s}" for s in urgent_subjects) if urgent_subjects else "None"

        prompt = f"""Summarize this daily email activity in 2-4 concise sentences. Focus on what matters most and any actions needed.

STATS:
- Total emails received: {total}
- Categories: {category_str}
- Urgent emails needing attention: {len(urgent)}
- Urgent subjects:
{urgent_str}
- Reply suggestions: {suggestions.get('total', 0)} total, {suggestions.get('pending', 0)} pending, {suggestions.get('accepted', 0)} accepted, {suggestions.get('rejected', 0)} rejected

Write a brief, natural-language summary highlighting the most important items. Do not use bullet points. Be conversational but professional."""

        response = await self.client.chat.completions.create(
            model=self.summarization_model,
            messages=[
                {"role": "system", "content": "You are a concise email activity summarizer. Respond with plain text only, no JSON or formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200,
        )

        summary = response.choices[0].message.content.strip()

        logger.info(
            "digest_summary_generated",
            provider=self.provider,
            total_emails=total,
            summary_length=len(summary),
        )

        return summary

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Note: Groq doesn't support embeddings yet
        Falls back to a simple hash-based vector for Groq
        For production with Groq, use a separate embedding service
        """
        if self.provider == "openai":
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        else:
            # Groq doesn't have embeddings - would need separate service
            # For now, return a warning
            logger.warning(
                "embedding_not_supported",
                provider=self.provider,
                note="Use OpenAI or separate embedding service for vector search"
            )
            # Return a dummy embedding for demo purposes
            import hashlib
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            # Generate pseudo-random 1536-dim vector from hash
            import random
            random.seed(hash_val)
            return [random.random() for _ in range(1536)]

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        if "```json" in content:
            try:
                return json.loads(content.split("```json")[1].split("```")[0].strip())
            except json.JSONDecodeError:
                pass
        elif "```" in content:
            try:
                return json.loads(content.split("```")[1].split("```")[0].strip())
            except json.JSONDecodeError:
                pass

        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.error("json_parse_failed", content=content[:200])
        raise ValueError(f"Could not parse JSON from LLM response: {content[:200]}")

    def _build_style_instructions(self, style_profile: Dict[str, Any]) -> str:
        if not style_profile:
            return "Use a professional, neutral tone."

        instructions = []

        # Feedback-learned preferences override base profile when available
        adjustments = style_profile.get("feedback_adjustments", {})

        tone = adjustments.get("preferred_tone") or style_profile.get("tone")
        if tone:
            instructions.append(f"Tone: {tone}")

        formality = adjustments.get("preferred_formality") or style_profile.get("formality")
        if formality:
            instructions.append(f"Formality: {formality}")

        avg_length = adjustments.get("avg_edited_length") or style_profile.get("avg_length")
        if avg_length:
            instructions.append(f"Target length: ~{avg_length} words")

        greetings = adjustments.get("preferred_greetings") or style_profile.get("greeting_patterns")
        if greetings:
            instructions.append(f"Typical greetings: {', '.join(greetings[:3])}")

        signoffs = adjustments.get("preferred_signoffs") or style_profile.get("signoff_patterns")
        if signoffs:
            instructions.append(f"Typical signoffs: {', '.join(signoffs[:3])}")

        if style_profile.get("emoji_usage", 0) > 0.2:
            instructions.append("User occasionally uses emojis")

        # Add specific correction patterns the LLM should follow
        corrections = adjustments.get("correction_patterns", [])
        if corrections:
            avoid_lines = []
            for c in corrections[:5]:
                avoid_lines.append(f'  - Instead of "{c["original_phrase"]}", use "{c["corrected_to"]}"')
            instructions.append("Phrasing preferences (from user edits):\n" + "\n".join(avoid_lines))

        return "\n".join(instructions) if instructions else "Use a professional, neutral tone."

    def _build_contact_context(self, contact: Dict[str, Any]) -> str:
        if not contact:
            return "Unknown sender."

        lines = []
        name = contact.get("name", "Unknown")
        lines.append(f"Name: {name}")

        if contact.get("company"):
            lines.append(f"Company: {contact['company']}")
        elif contact.get("domain"):
            lines.append(f"Domain: {contact['domain']}")

        if contact.get("known_contact"):
            lines.append(f"Emails exchanged: {contact.get('email_count', 0)}")

            topics = contact.get("topics", [])
            if topics:
                lines.append(f"Topics discussed: {', '.join(topics[:8])}")

            if contact.get("relationship_type"):
                lines.append(f"Relationship: {contact['relationship_type']}")

            if contact.get("interaction_summary"):
                lines.append(f"Summary: {contact['interaction_summary']}")
        else:
            lines.append("New contact (no prior history)")

        return "\n".join(lines)


    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def extract_tasks(self, email_content: str, subject: str, sender: str) -> Dict[str, Any]:
        """Extract actionable tasks from an email (excludes calendar/meeting items)."""
        from datetime import date as date_cls
        today = date_cls.today()

        prompt = f"""Analyze this email and extract any actionable tasks or action items mentioned.

Today is {today.isoformat()} ({today.strftime('%A')}).

Subject: {subject}
From: {sender}
Content: {email_content}

RULES:
- Extract tasks that require the recipient to DO something (e.g., "review the PR", "send the report", "commit the code", "update the document")
- Do NOT include calendar/meeting/scheduling items (those are handled separately)
- Do NOT include vague or social items like "let me know" or "hope you're well"
- Each task should be a clear, actionable item
- If no actionable tasks are found, return an empty tasks array

Return JSON with:
- has_tasks: boolean (true if there are actionable tasks)
- tasks: array of objects, each with:
  - title: string (concise task description, imperative form, e.g., "Review the PR for auth module")
  - priority: string ("low", "normal", "high", "urgent")
  - due_date: string or null (ISO date if a deadline is mentioned, null otherwise)
  - reasoning: string (brief explanation of why this is a task)
"""

        response = await self.client.chat.completions.create(
            model=self.classification_model,
            messages=[
                {"role": "system", "content": "You are a task extraction system. Analyze emails for actionable items the recipient needs to complete. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content
        result = self._parse_json_response(content)

        logger.info(
            "tasks_extracted",
            provider=self.provider,
            has_tasks=result.get("has_tasks"),
            task_count=len(result.get("tasks", []))
        )

        return result

    async def detect_meeting_acceptance(
        self,
        email_body: str,
        original_subject: str,
        proposed_meeting: str,
    ) -> Dict[str, Any]:
        """Detect if an email is a positive response to a meeting proposal.

        Returns {"accepted": true/false, "confidence": 0.0-1.0}
        """
        prompt = f"""Analyze this email and determine if it is a POSITIVE response accepting a meeting proposal.

Original meeting subject: "{original_subject}"
Proposed meeting: "{proposed_meeting}"

Email response:
{email_body}

Respond with ONLY valid JSON: {{"accepted": true/false, "confidence": 0.0-1.0}}

Rules:
- "accepted": true if the person is agreeing/confirming (e.g., "yes", "works for me", "sounds good", "see you then", "confirmed")
- "accepted": false if declining, asking to reschedule, or unrelated
- "confidence": how confident you are (0.0 to 1.0)"""

        try:
            response = await self.client.chat.completions.create(
                model=self.classification_model,
                messages=[
                    {"role": "system", "content": "You detect meeting acceptance in emails. Reply with ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=50,
            )
            result = self._parse_json_response(response.choices[0].message.content)
            logger.info("meeting_acceptance_detected",
                        accepted=result.get("accepted"),
                        confidence=result.get("confidence"))
            return result
        except Exception as e:
            logger.warning("meeting_acceptance_detection_failed", error=str(e))
            return {"accepted": False, "confidence": 0}

    async def chat_with_context(
        self,
        user_message: str,
        inbox_context: str,
    ) -> Dict[str, Any]:
        """Answer user questions about their inbox using LLM.

        Returns a dict with either:
          {"type": "email_draft", "email_draft": {"to": ..., "subject": ..., "body": ...}}
          {"type": "text", "reply": "..."}
        """
        prompt = f"""You are ECHO, an AI email assistant. The user is asking you a question.
Answer based on their context below. Be concise, helpful, and conversational.

CONTEXT:
{inbox_context}

USER MESSAGE:
{user_message}

RULES:
- If the user asks to directly SET, CREATE, or SCHEDULE a meeting/standup/call (e.g., "set a standup for 10pm", "schedule a meeting for Wednesday"), respond with ONLY valid JSON: {{"type": "calendar", "title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_minutes": 60, "project": "..."}}. Use 24-hour format for time. Set "project" to the project name if mentioned. Today's date is {datetime.utcnow().strftime('%Y-%m-%d')} ({datetime.utcnow().strftime('%A')}).
- If the user asks to ASK someone about a meeting or CHECK if a time works (e.g., "ask if 10pm works", "email them to see if Tuesday works"), respond with the email draft JSON: {{"to": "...", "subject": "...", "body": "..."}}. This is asking, NOT directly scheduling.
- If the user asks you to draft, compose, write, or send an email (non-meeting), respond with ONLY a valid JSON object: {{"to": "...", "subject": "...", "body": "..."}}. Do NOT include any text before or after the JSON. For the "to" field, put exactly what the user said — their name, email, or however they referred to the recipient (e.g., "alishba", "john@example.com", "AI Payroll team"). If they refer to a project team (e.g., "people I'm working with on X", "team on Y project"), set "to" to just the project name (e.g., "AI Payroll"). NEVER leave "to" empty if the user mentioned a recipient.
- For meeting/calendar questions (NOT creating), ONLY report events listed in "Upcoming calendar events" above. Do NOT guess or infer meetings from email subjects. State EXACTLY the event name and time as shown.
- Never combine or rename events. Each event is listed separately with its exact title and time.
- For all other questions, respond naturally in 1-3 sentences in plain text.
- If you don't have the information, say so."""

        try:
            response = await self.client.chat.completions.create(
                model=self.summarization_model,
                messages=[
                    {"role": "system", "content": "You are ECHO, a friendly AI email assistant. When the user asks to directly schedule/set a meeting, respond with ONLY valid JSON: {\"type\": \"calendar\", \"title\": \"...\", \"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\", \"duration_minutes\": 60, \"project\": \"...\"}. When the user asks to draft/compose/send an email (or ASK someone about a meeting time), respond with ONLY valid JSON: {\"to\": \"...\", \"subject\": \"...\", \"body\": \"...\"}. For all other questions, reply in plain text. When reporting calendar events, quote the exact event names and times from the context — never paraphrase or guess."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
            )

            reply = response.choices[0].message.content.strip()
            logger.info("chat_response_generated", provider=self.provider, reply_length=len(reply))

            # Try to detect if this is a structured JSON response
            try:
                parsed = self._parse_json_response(reply)
                if parsed.get("type") == "calendar" and "title" in parsed:
                    return {"type": "calendar_event", "calendar": parsed}
                if all(k in parsed for k in ("to", "subject", "body")):
                    return {"type": "email_draft", "email_draft": parsed}
            except (ValueError, json.JSONDecodeError):
                pass

            return {"type": "text", "reply": reply}
        except Exception as e:
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "429" in error_msg:
                logger.warning("chat_rate_limited", error=str(e))
                return {"type": "text", "reply": "I've hit my usage limit for now. Please try again in a few minutes."}
            logger.error("chat_llm_error", error=str(e))
            raise


llm_router = MultiProviderLLMRouter()
