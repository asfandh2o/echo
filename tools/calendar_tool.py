from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.security import token_encryption
from core.logging import get_logger
from datetime import datetime, timedelta
import json

logger = get_logger(__name__)


class CalendarTool:
    def __init__(self, encrypted_tokens: str, user_id: str):
        self.encrypted_tokens = encrypted_tokens
        self.user_id = user_id
        self.service = None

    async def _get_service(self):
        if self.service:
            return self.service

        decrypted = token_encryption.decrypt(self.encrypted_tokens)
        token_data = json.loads(decrypted)

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
        )

        self.service = build("calendar", "v3", credentials=credentials)
        return self.service

    async def get_upcoming_events(self, days_ahead: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            service = await self._get_service()

            now = datetime.utcnow().isoformat() + "Z"
            end_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

            events_result = service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=end_time,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])

            formatted_events = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

                formatted_events.append({
                    "id": event["id"],
                    "summary": event.get("summary", "No title"),
                    "start": start,
                    "end": end,
                    "location": event.get("location"),
                    "attendees": [a.get("email") for a in event.get("attendees", [])],
                    "description": event.get("description")
                })

            logger.info("calendar_events_fetched", user_id=self.user_id, count=len(formatted_events))

            return formatted_events

        except HttpError as error:
            logger.error("calendar_fetch_error", user_id=self.user_id, error=str(error))
            raise

    async def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: List[str] = None,
        description: str = None,
        location: str = None
    ) -> Dict[str, Any]:
        try:
            service = await self._get_service()

            # TODO: make timezone configurable per user
            event_body = {
                "summary": summary,
                "start": {"dateTime": start_time, "timeZone": "Asia/Karachi"},
                "end": {"dateTime": end_time, "timeZone": "Asia/Karachi"},
            }

            if attendees:
                event_body["attendees"] = [{"email": email} for email in attendees]

            if description:
                event_body["description"] = description

            if location:
                event_body["location"] = location

            event = service.events().insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="all"
            ).execute()

            logger.info(
                "calendar_event_created",
                user_id=self.user_id,
                event_id=event["id"],
                summary=summary
            )

            return {
                "id": event["id"],
                "summary": event.get("summary"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "html_link": event.get("htmlLink"),
                "attendees": [a.get("email") for a in event.get("attendees", [])],
                "status": event.get("status")
            }

        except HttpError as error:
            logger.error("calendar_create_error", user_id=self.user_id, error=str(error))
            raise

    async def update_event(
        self,
        event_id: str,
        summary: str = None,
        start_time: str = None,
        end_time: str = None,
        attendees: List[str] = None,
        description: str = None,
        location: str = None
    ) -> Dict[str, Any]:
        try:
            service = await self._get_service()

            existing = service.events().get(
                calendarId="primary", eventId=event_id
            ).execute()

            if summary:
                existing["summary"] = summary
            if start_time:
                existing["start"] = {"dateTime": start_time, "timeZone": "Asia/Karachi"}
            if end_time:
                existing["end"] = {"dateTime": end_time, "timeZone": "Asia/Karachi"}
            if attendees is not None:
                existing["attendees"] = [{"email": email} for email in attendees]
            if description:
                existing["description"] = description
            if location:
                existing["location"] = location

            updated = service.events().update(
                calendarId="primary",
                eventId=event_id,
                body=existing,
                sendUpdates="all"
            ).execute()

            logger.info(
                "calendar_event_updated",
                user_id=self.user_id,
                event_id=event_id
            )

            return {
                "id": updated["id"],
                "summary": updated.get("summary"),
                "start": updated["start"].get("dateTime", updated["start"].get("date")),
                "end": updated["end"].get("dateTime", updated["end"].get("date")),
                "html_link": updated.get("htmlLink"),
                "attendees": [a.get("email") for a in updated.get("attendees", [])],
                "status": updated.get("status")
            }

        except HttpError as error:
            logger.error("calendar_update_error", user_id=self.user_id, error=str(error))
            raise

    async def find_event_by_query(
        self, query: str, time_min: str = None, time_max: str = None
    ) -> Optional[Dict[str, Any]]:
        try:
            service = await self._get_service()

            if not time_min:
                time_min = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
            if not time_max:
                time_max = (datetime.utcnow() + timedelta(days=90)).isoformat() + "Z"

            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                q=query,
                singleEvents=True,
                orderBy="startTime",
                maxResults=5
            ).execute()

            events = events_result.get("items", [])

            if not events:
                return None

            event = events[0]
            return {
                "id": event["id"],
                "summary": event.get("summary", "No title"),
                "start": event["start"].get("dateTime", event["start"].get("date")),
                "end": event["end"].get("dateTime", event["end"].get("date")),
                "attendees": [a.get("email") for a in event.get("attendees", [])],
                "description": event.get("description")
            }

        except HttpError as error:
            logger.error("calendar_search_error", user_id=self.user_id, error=str(error))
            return None

    async def get_free_slots(
        self,
        around_time: str,
        duration_minutes: int = 60,
        search_days: int = 3,
        max_slots: int = 3
    ) -> List[Dict[str, Any]]:
        """Find free time slots around a proposed time for suggesting alternatives."""
        try:
            service = await self._get_service()

            proposed = datetime.fromisoformat(around_time.replace("Z", "+00:00"))
            search_start = proposed.replace(hour=8, minute=0, second=0, microsecond=0)
            search_end = (search_start + timedelta(days=search_days)).replace(hour=20, minute=0)

            body = {
                "timeMin": search_start.isoformat(),
                "timeMax": search_end.isoformat(),
                "items": [{"id": "primary"}]
            }

            freebusy_result = service.freebusy().query(body=body).execute()
            busy_times = freebusy_result.get("calendars", {}).get("primary", {}).get("busy", [])

            busy_periods = []
            for busy in busy_times:
                busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
                busy_periods.append((busy_start, busy_end))

            busy_periods.sort(key=lambda x: x[0])

            free_slots = []
            current_day = search_start

            while current_day < search_end and len(free_slots) < max_slots:
                slot_start = current_day.replace(hour=8, minute=0, second=0, microsecond=0)
                day_end = current_day.replace(hour=20, minute=0, second=0, microsecond=0)

                while slot_start + timedelta(minutes=duration_minutes) <= day_end and len(free_slots) < max_slots:
                    slot_end = slot_start + timedelta(minutes=duration_minutes)

                    is_free = True
                    for busy_start, busy_end in busy_periods:
                        if slot_start < busy_end and slot_end > busy_start:
                            is_free = False
                            slot_start = busy_end
                            break

                    if is_free:
                        if slot_start != proposed:
                            free_slots.append({
                                "start": slot_start.isoformat(),
                                "end": slot_end.isoformat()
                            })
                        slot_start = slot_end
                    # if not free, slot_start was already advanced to busy_end

                current_day += timedelta(days=1)

            logger.info(
                "free_slots_found",
                user_id=self.user_id,
                count=len(free_slots)
            )

            return free_slots

        except HttpError as error:
            logger.error("free_slots_error", user_id=self.user_id, error=str(error))
            return []

    async def get_conflicting_events(self, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        """Get the actual events that conflict with a proposed time."""
        try:
            service = await self._get_service()

            events_result = service.events().list(
                calendarId="primary",
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])
            return [
                {
                    "id": event["id"],
                    "summary": event.get("summary", "Busy"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "attendees": event.get("attendees", []),
                    "organizer": event.get("organizer", {}),
                }
                for event in events
            ]

        except HttpError as error:
            logger.error("conflicting_events_error", user_id=self.user_id, error=str(error))
            return []

    async def check_availability(self, start_time: str, end_time: str) -> bool:
        try:
            service = await self._get_service()

            body = {
                "timeMin": start_time,
                "timeMax": end_time,
                "items": [{"id": "primary"}]
            }

            freebusy_result = service.freebusy().query(body=body).execute()

            busy_times = freebusy_result.get("calendars", {}).get("primary", {}).get("busy", [])

            is_available = len(busy_times) == 0

            logger.info(
                "availability_checked",
                user_id=self.user_id,
                available=is_available,
                busy_slots=len(busy_times)
            )

            return is_available

        except HttpError as error:
            logger.error("availability_check_error", user_id=self.user_id, error=str(error))
            raise
