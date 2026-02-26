"""LLM formatting service using Ollama."""
import json
import logging
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingStatus, Transcript, Minute

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """You are a meeting minutes assistant. Given the raw transcript below, produce structured meeting minutes in JSON format with these keys:
- overview: 2-3 sentence summary of the meeting
- discussion_highlights: list of key discussion points
- action_items: list of objects with keys: description, assignee (or null), due_date (YYYY-MM-DD or null)
- key_decisions: list of decisions made

Output ONLY valid JSON, no markdown or explanation.

Transcript:
"""


def format_transcript_with_ollama(raw_text: str) -> dict[str, Any]:
    """Call Ollama to format transcript into structured minutes."""
    import httpx

    prompt = DEFAULT_PROMPT + raw_text

    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        r.raise_for_status()
        data = r.json()
        response_text = data.get("response", "")

    # Parse JSON from response (handle markdown code blocks)
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            line for line in lines
            if not line.startswith("```") and line.strip()
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Ollama returned invalid JSON, using fallback")
        return {
            "overview": raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
            "discussion_highlights": [],
            "action_items": [],
            "key_decisions": [],
        }


def _to_markdown(content: dict[str, Any]) -> str:
    """Convert structured content to markdown."""
    parts = []

    if overview := content.get("overview"):
        parts.append("## Overview\n\n" + overview)

    if highlights := content.get("discussion_highlights"):
        parts.append("\n## Discussion Highlights\n")
        for h in highlights:
            parts.append(f"- {h}")

    if items := content.get("action_items"):
        parts.append("\n## Action Items\n")
        for item in items:
            desc = item.get("description", "")
            assignee = item.get("assignee", "")
            due = item.get("due_date", "")
            line = f"- {desc}"
            if assignee:
                line += f" (@{assignee})"
            if due:
                line += f" — Due: {due}"
            parts.append(line)

    if decisions := content.get("key_decisions"):
        parts.append("\n## Key Decisions\n")
        for d in decisions:
            parts.append(f"- {d}")

    return "\n".join(parts)


def format_meeting_sync(meeting_id: int) -> None:
    """Format meeting transcript into minutes and save to DB."""
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return

        transcript = (
            db.query(Transcript)
            .filter(Transcript.meeting_id == meeting_id)
            .first()
        )
        if not transcript:
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = "No transcript to format"
            db.commit()
            return

        try:
            content = format_transcript_with_ollama(transcript.raw_text)
            markdown = _to_markdown(content)

            minute = Minute(
                meeting_id=meeting_id,
                formatted_content=content,
                model_used=settings.ollama_model,
                markdown=markdown,
            )
            db.add(minute)

            meeting.status = MeetingStatus.FORMATTED
            db.commit()

        except Exception as e:
            logger.exception("Formatting failed for meeting %s", meeting_id)
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = str(e)[:1024]
            db.commit()
    finally:
        db.close()
