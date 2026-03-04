"""LLM formatting service using Ollama."""
import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingStatus, Project, Template, Transcript, Minute
from app.models.template import DEFAULT_STRUCTURE
from app.services.progress import clear_progress, set_progress

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """You are a meeting minutes assistant. Transform the raw transcript into concise, structured meeting minutes.

RULES:
- overview: 2-3 short sentences summarizing the meeting purpose and main outcome. Do NOT copy the transcript verbatim.
- discussion_highlights: 3-8 bullet points of key topics discussed (one concise line each)
- action_items: tasks with description, assignee (or null), due_date (YYYY-MM-DD or null). Extract any commitments or next steps.
- key_decisions: decisions or agreements made (one line each)

Return ONLY valid JSON. No markdown, no code fences, no explanation. Example structure:
{"overview":"Brief summary here.","discussion_highlights":["Point 1","Point 2"],"action_items":[{"description":"Task","assignee":null,"due_date":null}],"key_decisions":["Decision 1"]}
"""


def _fallback_content(raw_text: str) -> dict[str, Any]:
    """Fallback when Ollama is unavailable or returns invalid JSON."""
    # Create structured content from raw text: overview + bullet highlights
    sentences = [s.strip() for s in re.split(r"[.!?]+", raw_text) if len(s.strip()) > 20]
    overview = " ".join(sentences[:2]).strip() if sentences else raw_text[:300]
    if len(overview) > 400:
        overview = overview[:397] + "..."
    if not overview:
        overview = raw_text[:300] + ("..." if len(raw_text) > 300 else "")

    # Use first 5–8 substantial sentences as discussion highlights (skip very short)
    highlights = [s for s in sentences[2:10] if len(s) > 30][:6]

    return {
        "overview": overview,
        "discussion_highlights": highlights,
        "action_items": [],
        "key_decisions": [],
    }


# Conservative chars per token (English); used to stay under context limit
CHARS_PER_TOKEN = 4

# Max chars of template sample to send so the prompt stays manageable
MAX_TEMPLATE_SAMPLE_CHARS = 8_000


def _estimate_tokens(text: str) -> int:
    """Rough token count so we stay under context window."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def _max_transcript_chars_per_chunk() -> int:
    """Max transcript characters per LLM call so prompt + response fits in context."""
    context = getattr(settings, "ollama_context_tokens", 4096)
    max_out = getattr(settings, "ollama_max_output_tokens", 2048)
    # Reserve for: instruction + template + "segment N/M" + JSON response
    reserved = 800  # tokens for prompt prefix (instruction + short template)
    budget_tokens = max(500, context - max_out - reserved)
    return budget_tokens * CHARS_PER_TOKEN


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split transcript at paragraph/sentence boundaries so chunks fit in context."""
    text = (text or "").strip()
    if not text or len(text) <= max_chars:
        return [text] if text else []
    chunks: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_chars:
            chunks.append(rest.strip())
            break
        # Prefer split at double newline (paragraph), then single newline, then sentence end
        segment = rest[: max_chars + 1]
        split_at = -1
        for sep in ("\n\n", "\n", ". ", "? ", "! "):
            idx = segment.rfind(sep)
            if idx > max_chars // 2:  # avoid tiny tail chunk
                split_at = idx + len(sep)
                break
        if split_at <= 0:
            split_at = max_chars
        chunks.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()
    return [c for c in chunks if c]


def _merge_chunk_results(chunk_results: list[dict[str, Any]], raw_text: str) -> dict[str, Any]:
    """Merge per-chunk JSON outputs into one structured minutes."""
    if not chunk_results:
        return _fallback_content(raw_text)
    if len(chunk_results) == 1:
        return chunk_results[0]
    overviews = []
    all_highlights: list[str] = []
    all_actions: list[dict[str, Any]] = []
    all_decisions: list[str] = []
    for r in chunk_results:
        if r.get("overview"):
            overviews.append(r["overview"])
        all_highlights.extend(r.get("discussion_highlights") or [])
        all_actions.extend(r.get("action_items") or [])
        all_decisions.extend(r.get("key_decisions") or [])
    overview = " ".join(overviews[:3]).strip() if overviews else ""
    if len(overview) > 800:
        overview = overview[:797] + "..."
    # Dedupe by normalizing and comparing
    def _dedupe_str(items: list[str], key=None) -> list[str]:
        seen = set()
        out = []
        for x in items:
            n = (key(x) if key else x).strip().lower()
            if n and n not in seen:
                seen.add(n)
                out.append(x.strip() if isinstance(x, str) else x)
        return out

    def _dedupe_actions(items: list[dict]) -> list[dict]:
        seen = set()
        out = []
        for x in items:
            desc = (x.get("description") or "").strip()
            if not desc:
                continue
            key = desc.lower()[:80]
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out

    return {
        "overview": overview or "Meeting covered multiple topics.",
        "discussion_highlights": _dedupe_str(all_highlights)[:20],
        "action_items": _dedupe_actions(all_actions)[:30],
        "key_decisions": _dedupe_str(all_decisions)[:20],
    }


def _call_ollama_single(
    prompt: str,
    meeting_id: int | None = None,
    segment_index: int | None = None,
    segment_total: int | None = None,
) -> dict[str, Any]:
    """Single Ollama call with given prompt; returns parsed JSON or raises."""
    import httpx

    max_out = getattr(settings, "ollama_max_output_tokens", 2048)
    with httpx.Client(timeout=180.0) as client:
        r = client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                    "num_predict": max_out,
                },
            },
        )
        r.raise_for_status()
        data = r.json()
    response_text = (data.get("response") or "").strip()
    if not response_text:
        err = data.get("error") if isinstance(data, dict) else None
        logger.warning(
            "Ollama returned empty response. Model=%s. %s",
            settings.ollama_model,
            f"Ollama error: {err}." if err else "No response text.",
        )
        return {}
    text = _extract_and_clean_json(response_text)
    if not text or "{" not in text:
        return {}
    try:
        return _parse_json_with_fixups(text, "")
    except json.JSONDecodeError:
        return {}


def format_transcript_with_ollama(
    raw_text: str,
    prompt_suffix: str | None = None,
    template_sample: str | None = None,
    meeting_id: int | None = None,
) -> dict[str, Any]:
    """Format transcript with Ollama. Chunks long transcripts to fit context window (e.g. 4096 for qwen3.5)."""
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return _fallback_content(raw_text)

    max_chars = _max_transcript_chars_per_chunk()
    # Keep template small when chunking so we leave room for transcript
    template_cap = min(MAX_TEMPLATE_SAMPLE_CHARS, max(2000, max_chars // 2))
    sample = (template_sample or "").strip()
    if sample and len(sample) > template_cap:
        sample = sample[:template_cap] + "\n\n[... template truncated ...]"

    prompt_prefix = DEFAULT_PROMPT
    if sample:
        prompt_prefix += (
            "\n\nCLIENT'S TEMPLATE FORMAT (match this structure):\n---\n"
            + sample
            + "\n---\n\n"
        )
    if prompt_suffix:
        prompt_prefix += "\n\nADDITIONAL INSTRUCTIONS:\n" + prompt_suffix.strip() + "\n\n"
    prefix_tokens = _estimate_tokens(prompt_prefix)
    # Reserve tokens for "TRANSCRIPT (segment N/M):" and response
    max_out = getattr(settings, "ollama_max_output_tokens", 2048)
    context = getattr(settings, "ollama_context_tokens", 4096)
    chunk_budget_tokens = max(400, context - max_out - prefix_tokens - 50)
    max_chars_per_chunk = chunk_budget_tokens * CHARS_PER_TOKEN

    chunks = _split_into_chunks(raw_text, max_chars_per_chunk)
    if not chunks:
        return _fallback_content(raw_text)

    if len(chunks) == 1:
        prompt = prompt_prefix + "\nTRANSCRIPT:\n" + chunks[0]
        if meeting_id is not None:
            set_progress(meeting_id, "Generating minutes with Ollama...")
        result = _call_ollama_single(prompt)
        if result:
            return result
        return _fallback_content(raw_text)
    # Multi-chunk: format each segment then merge
    chunk_results: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        if meeting_id is not None:
            set_progress(
                meeting_id,
                "Formatting segment %d of %d..." % (i + 1, len(chunks)),
            )
        segment_note = "\n(This is segment %d of %d. Extract minutes for this part only.)\n\n" % (
            i + 1,
            len(chunks),
        )
        prompt = prompt_prefix + segment_note + "TRANSCRIPT:\n" + chunk
        result = _call_ollama_single(prompt, meeting_id, i + 1, len(chunks))
        if result:
            chunk_results.append(result)
    if not chunk_results:
        return _fallback_content(raw_text)
    merged = _merge_chunk_results(chunk_results, raw_text)
    logger.info(
        "Merged %d segment(s) for context window (total %d chars)",
        len(chunk_results),
        len(raw_text),
    )
    return merged


def _extract_and_clean_json(response_text: str) -> str:
    """Extract JSON object from LLM response and apply basic cleanups."""
    text = (response_text or "").strip()
    # Strip markdown code blocks (```json ... ``` or ``` ... ```)
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    # Extract first complete {...} object (from first { to matching })
    if "{" in text:
        start = text.index("{")
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > start:
            text = text[start:end]
        elif start >= 0:
            # Truncated: no matching }. Use from { to last } and hope it's salvageable
            last_brace = text.rfind("}", start)
            if last_brace > start:
                text = text[start : last_brace + 1]
            else:
                text = text[start:]
    # Fix trailing commas (invalid in strict JSON)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _parse_json_with_fixups(text: str, raw_text: str) -> dict[str, Any]:
    """Try to parse JSON, applying fixups for common LLM mistakes."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fix unquoted keys (e.g. overview: -> "overview":) for known keys
    for key in ("overview", "discussion_highlights", "action_items", "key_decisions", "description", "assignee", "due_date"):
        text = re.sub(rf"\b{re.escape(key)}\s*:", rf'"{key}":', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Remove trailing garbage after last }
    last_brace = text.rfind("}")
    if last_brace != -1:
        try:
            return json.loads(text[: last_brace + 1])
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("Could not parse after fixups", text, 0)


def _sanitize_llm_content(content: dict[str, Any], raw_text: str) -> dict[str, Any]:
    """If LLM returned a verbatim copy instead of summary, improve it."""
    overview = content.get("overview") or ""
    # Overview should be a summary, not a long transcript copy
    if len(overview) > 600 and raw_text.strip().startswith(overview[:100]):
        logger.info("LLM returned verbatim transcript as overview, applying smart fallback")
        return _fallback_content(raw_text)
    return content


def _to_markdown(
    content: dict[str, Any],
    structure: dict[str, str] | None = None,
) -> str:
    """Convert structured content to markdown. structure maps JSON keys to section titles (e.g. overview -> Overview)."""
    structure = structure or DEFAULT_STRUCTURE
    parts = []

    if overview := content.get("overview"):
        title = structure.get("overview", "Overview")
        parts.append(f"## {title}\n\n{overview}")

    if highlights := content.get("discussion_highlights"):
        title = structure.get("discussion_highlights", "Discussion Highlights")
        parts.append(f"\n## {title}\n")
        for h in highlights:
            parts.append(f"- {h}")

    if items := content.get("action_items"):
        title = structure.get("action_items", "Action Items")
        parts.append(f"\n## {title}\n")
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
        title = structure.get("key_decisions", "Key Decisions")
        parts.append(f"\n## {title}\n")
        for d in decisions:
            parts.append(f"- {d}")

    return "\n".join(parts)


def _resolve_template_for_meeting(meeting: Meeting, db) -> Template | None:
    """Resolve template: meeting override, then project default."""
    if meeting.template_id:
        t = db.query(Template).filter(Template.id == meeting.template_id).first()
        if t:
            return t
    if meeting.project_id:
        project = db.query(Project).filter(Project.id == meeting.project_id).first()
        if project and project.default_template_id:
            return db.query(Template).filter(Template.id == project.default_template_id).first()
    return None


def format_meeting_sync(meeting_id: int) -> None:
    """Format meeting transcript into minutes and save to DB. Uses meeting or project template if set."""
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
            clear_progress(meeting_id)
            db.commit()
            return

        template = _resolve_template_for_meeting(meeting, db)
        prompt_suffix = template.prompt_suffix if template else None
        template_sample = template.sample_content if template else None
        structure = template.structure if template else None

        try:
            set_progress(meeting_id, "Generating minutes with Ollama...")
            try:
                content = format_transcript_with_ollama(
                    transcript.raw_text,
                    prompt_suffix=prompt_suffix,
                    template_sample=template_sample,
                    meeting_id=meeting_id,
                )
                content = _sanitize_llm_content(content, transcript.raw_text)
                model_used = settings.ollama_model
            except Exception as e:
                logger.warning("Ollama unavailable (%s), using fallback minutes", e)
                content = _fallback_content(transcript.raw_text)
                model_used = "fallback (Ollama unavailable)"

            markdown = _to_markdown(content, structure=structure)

            minute = Minute(
                meeting_id=meeting_id,
                formatted_content=content,
                template_id=template.id if template else None,
                model_used=model_used,
                markdown=markdown,
            )
            db.add(minute)

            meeting.status = MeetingStatus.FORMATTED
            meeting.error_message = None
            db.commit()

        except Exception as e:
            logger.exception("Formatting failed for meeting %s", meeting_id)
            meeting.status = MeetingStatus.ERROR
            meeting.error_message = str(e)[:1024]
            clear_progress(meeting_id)
            db.commit()
    finally:
        db.close()
