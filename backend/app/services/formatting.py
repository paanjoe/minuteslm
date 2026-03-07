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

# When template has format_spec_markdown, we ask for markdown output following that structure
MARKDOWN_FORMAT_PROMPT = """You are a meeting minutes assistant. Output minutes in the structure below, formatted as clean markdown (like a GitHub README) so it is easy to read.

RULES:
- Use ONLY the section titles from "OUTPUT FORMAT" below, in the same order. Do NOT add "Overview", "Discussion Highlights", or any sections not in that list.
- Format for readability:
  - Use **bold** for field labels (e.g. **Project Name:** value). Put each label-value pair on its own line.
  - For lists (e.g. Attendee, Action Items): use markdown bullet list, one item per line, e.g. "- Item one" and "- Item two". Do NOT use semicolons in a single line.
  - Add a blank line between sections. Use ## for a section heading if it fits (e.g. ## Action Items).
- Do NOT output JSON. Do NOT use code fences (```). No explanation or preamble.
- Return only the filled-in markdown, same section order as OUTPUT FORMAT.

EXTRACTION:
- Fill each section only from what is clearly stated in the transcript.
- If a detail is not given, leave the value blank but keep the label (e.g. **Minutes Taken By:** with nothing after it).
- Do not infer or guess; do not write "[Not specified]"—just blank after the label.

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


# Conservative chars per token (English); use 3.5 so we stay under Qwen context
CHARS_PER_TOKEN = 3

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


def _head_tail_text(text: str, max_chars: int, middle_label: str = "\n\n[... middle of transcript omitted for length ...]\n\n") -> str:
    """For long transcripts, return start + middle label + end so LLM sees opening and closing."""
    text = (text or "").strip()
    if not text or len(text) <= max_chars:
        return text
    half = max(500, (max_chars - len(middle_label)) // 2)
    return text[:half] + middle_label + text[-half:]


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
                "think": False,  # Qwen 3.5: put answer in "response", not "thinking"
                "options": {
                    "temperature": 0,
                    "num_predict": max_out,
                },
            },
        )
        r.raise_for_status()
        data = r.json()
    response_text = (data.get("response") or "").strip()
    if not response_text and data.get("thinking"):
        response_text = (data.get("thinking") or "").strip()
        if response_text:
            logger.info("Using Ollama 'thinking' field for JSON (response was empty)")
    if not response_text:
        err = data.get("error") if isinstance(data, dict) else None
        logger.warning(
            "Ollama returned empty response. Model=%s. keys=%s %s",
            settings.ollama_model,
            list(data.keys()) if isinstance(data, dict) else [],
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


def _extract_markdown_from_response(response_text: str) -> str:
    """Strip code fences from LLM response and return plain markdown. Reject JSON."""
    text = (response_text or "").strip()
    if "```" in text:
        match = re.search(r"```(?:markdown)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    if text.lstrip().startswith("{"):
        logger.warning("LLM returned JSON instead of markdown for format_spec; ignoring")
        return ""
    return text


def _call_ollama_markdown(prompt: str) -> str:
    """Call Ollama without format=json; return raw response as markdown."""
    import httpx

    max_out = getattr(settings, "ollama_max_output_tokens", 2048)
    base_payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": max_out},
    }
    # First try with think=False so Qwen 3.5 puts the answer in "response"
    with httpx.Client(timeout=180.0) as client:
        r = client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={**base_payload, "think": False},
        )
        r.raise_for_status()
        data = r.json()
    response_text = (data.get("response") or "").strip()
    if not response_text and data.get("thinking"):
        response_text = (data.get("thinking") or "").strip()
        if response_text:
            logger.info("Using Ollama 'thinking' field (response was empty)")
    # If still empty, retry with think=True and use "thinking" or "response" (some Qwen/Ollama versions need this)
    if not response_text:
        logger.info("Retrying with think=True to get output from Qwen")
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={**base_payload, "think": True},
            )
            r.raise_for_status()
            data = r.json()
        response_text = (data.get("response") or "").strip()
        if not response_text and data.get("thinking"):
            response_text = (data.get("thinking") or "").strip()
            if response_text:
                logger.info("Using Ollama 'thinking' field from think=True run")
    if not response_text:
        logger.warning(
            "Ollama returned empty response. model=%s keys=%s done=%s done_reason=%s eval_count=%s",
            settings.ollama_model,
            list(data.keys()),
            data.get("done"),
            data.get("done_reason"),
            data.get("eval_count"),
        )
        if data.get("error"):
            logger.warning("Ollama error field: %s", data.get("error"))
        return ""
    logger.info(
        "Ollama markdown response length=%d first_200=%r",
        len(response_text),
        response_text[:200],
    )
    extracted = _extract_markdown_from_response(response_text)
    if not extracted and response_text:
        logger.warning(
            "Ollama response was rejected by _extract_markdown (JSON or empty after strip). first_100=%r",
            response_text[:100],
        )
    return extracted


def build_format_prompt(
    raw_text: str,
    prompt_suffix: str | None = None,
    template_sample: str | None = None,
    format_spec_markdown: str | None = None,
    transcript_max_chars: int | None = None,
    summary_context: str | None = None,
) -> str:
    """
    Build the exact prompt that would be sent to Ollama (for the first/only chunk).
    Use for debugging or preview. transcript_max_chars caps the transcript in the prompt (None = use full chunk).
    """
    raw_text = (raw_text or "").strip()
    max_chars = _max_transcript_chars_per_chunk()
    template_cap = min(MAX_TEMPLATE_SAMPLE_CHARS, max(2000, max_chars // 2))
    format_spec_cap = min(MAX_TEMPLATE_SAMPLE_CHARS, 4000)

    if (format_spec_markdown or "").strip():
        prompt_prefix = MARKDOWN_FORMAT_PROMPT
        spec = (format_spec_markdown or "").strip()
        if len(spec) > format_spec_cap:
            spec = spec[:format_spec_cap] + "\n\n[... format spec truncated ...]"
        prompt_prefix += (
            "OUTPUT FORMAT (you must follow this structure exactly; fill in each section from the transcript):\n---\n"
            + spec
            + "\n---\n\n"
        )
        sample = (template_sample or "").strip()
        if sample and len(sample) > template_cap:
            sample = sample[:template_cap] + "\n\n[... template truncated ...]"
        if sample:
            prompt_prefix += "\nREFERENCE (optional):\n---\n" + sample + "\n---\n\n"
        if prompt_suffix:
            prompt_prefix += "\nADDITIONAL INSTRUCTIONS:\n" + prompt_suffix.strip() + "\n\n"
    else:
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

    context_block = ""
    if (summary_context or "").strip():
        context_block = "\nUSER CONTEXT (use for summary):\n" + (summary_context or "").strip() + "\n\n"
    if not raw_text:
        return prompt_prefix + context_block + "TRANSCRIPT:\n(empty)"
    max_show = transcript_max_chars if transcript_max_chars is not None else max_chars
    chunk = raw_text[:max_show]
    if len(raw_text) > max_show:
        chunk += "\n\n[... transcript truncated for preview ...]"
    return prompt_prefix + context_block + "TRANSCRIPT:\n" + chunk


def format_transcript_with_ollama(
    raw_text: str,
    prompt_suffix: str | None = None,
    template_sample: str | None = None,
    format_spec_markdown: str | None = None,
    meeting_id: int | None = None,
    summary_context: str | None = None,
) -> dict[str, Any]:
    """Format transcript with Ollama. When format_spec_markdown is set, asks for markdown output; otherwise JSON."""
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return _fallback_content(raw_text)

    format_spec = (format_spec_markdown or "").strip()
    if format_spec:
        # Markdown-output mode: single call, no chunking; prompt asks for markdown following format spec
        max_chars = _max_transcript_chars_per_chunk()
        format_spec_cap = min(MAX_TEMPLATE_SAMPLE_CHARS, 4000)
        spec = format_spec[:format_spec_cap] + ("\n\n[... truncated ...]" if len(format_spec) > format_spec_cap else "")
        prompt_prefix = MARKDOWN_FORMAT_PROMPT + (
            "OUTPUT FORMAT (you must follow this structure exactly; fill in each section from the transcript):\n---\n"
            + spec
            + "\n---\n\n"
        )
        template_cap = min(MAX_TEMPLATE_SAMPLE_CHARS, max(2000, max_chars // 2))
        sample = (template_sample or "").strip()
        if sample and len(sample) > template_cap:
            sample = sample[:template_cap] + "\n\n[... template truncated ...]"
        if sample:
            prompt_prefix += "\nREFERENCE (optional):\n---\n" + sample + "\n---\n\n"
        if prompt_suffix:
            prompt_prefix += "\nADDITIONAL INSTRUCTIONS:\n" + prompt_suffix.strip() + "\n\n"
        prompt_prefix += (
            "Remember: output only the sections from OUTPUT FORMAT above, in the same order. "
            "Fill in only what the transcript clearly gives; if a detail is not given, leave it blank after the title. No JSON.\n\n"
        )
        context_block = ""
        if (summary_context or "").strip():
            context_block = "USER CONTEXT (use for summary):\n" + (summary_context or "").strip() + "\n\n"
        prefix_tokens = _estimate_tokens(prompt_prefix)
        max_out = getattr(settings, "ollama_max_output_tokens", 2048)
        context = getattr(settings, "ollama_context_tokens", 4096)
        # Reserve 100 tokens buffer so we don't exceed Qwen context
        transcript_budget = max(500, (context - max_out - prefix_tokens - 100) * CHARS_PER_TOKEN)
        chunk = _head_tail_text(raw_text, transcript_budget)
        if len(raw_text) > transcript_budget:
            logger.info(
                "Long transcript: using head+tail (total=%d chars, budget=%d)",
                len(raw_text),
                transcript_budget,
            )
        prompt = prompt_prefix + context_block + "TRANSCRIPT:\n" + chunk
        if getattr(settings, "log_llm_prompt", False):
            logger.info("Ollama prompt (markdown mode, first 2500 chars):\n%s", prompt[:2500])
        if meeting_id is not None:
            set_progress(meeting_id, "Generating minutes with Ollama...", 85)
        markdown_content = _call_ollama_markdown(prompt)
        had_any_response = bool(markdown_content)
        # If model returned default structure instead of our format, treat as failure
        if markdown_content and (
            "## Overview" in markdown_content or "## Discussion Highlights" in markdown_content
        ):
            logger.warning("Model returned default structure despite format_spec; using placeholder")
            markdown_content = ""
        if markdown_content:
            return {"_markdown": markdown_content}
        # Model returned empty or wrong structure; do NOT fall back to JSON - keep user's format
        empty_response = not had_any_response
        placeholder = (
            "*The model did not follow the template format. Click Re-format to try again.*\n\n"
            + spec
            + "\n\n*(Fill the sections above from the transcript.)*"
        )
        if empty_response:
            placeholder = (
                "*Ollama returned no text. Ensure Ollama is running and the model is loaded.*\n\n"
                "Run in a terminal: `ollama run qwen3.5` then click Re-format.\n\n"
                "---\n\n"
                + spec
                + "\n\n*(Fill the sections above from the transcript.)*"
            )
        logger.warning("Format spec was set but model returned no valid markdown; using placeholder")
        return {"_markdown": placeholder, "_empty_response": empty_response}

    # JSON mode (existing behavior)
    max_chars = _max_transcript_chars_per_chunk()
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
    context_block = ""
    if (summary_context or "").strip():
        context_block = "USER CONTEXT (use for summary):\n" + (summary_context or "").strip() + "\n\n"
    prefix_tokens = _estimate_tokens(prompt_prefix)
    max_out = getattr(settings, "ollama_max_output_tokens", 2048)
    context = getattr(settings, "ollama_context_tokens", 4096)
    chunk_budget_tokens = max(400, context - max_out - prefix_tokens - 50)
    max_chars_per_chunk = chunk_budget_tokens * CHARS_PER_TOKEN

    chunks = _split_into_chunks(raw_text, max_chars_per_chunk)
    if not chunks:
        return _fallback_content(raw_text)

    if len(chunks) == 1:
        prompt = prompt_prefix + context_block + "TRANSCRIPT:\n" + chunks[0]
        if getattr(settings, "log_llm_prompt", False):
            logger.info("Ollama prompt (full):\n%s", prompt)
        if meeting_id is not None:
            set_progress(meeting_id, "Generating minutes with Ollama...", 85)
        result = _call_ollama_single(prompt)
        if result:
            return result
        return _fallback_content(raw_text)
    # Multi-chunk: format each segment then merge
    chunk_results: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        if meeting_id is not None:
            pct = 85 + int(14 * (i + 1) / len(chunks)) if len(chunks) else 85
            set_progress(
                meeting_id,
                "Formatting segment %d of %d..." % (i + 1, len(chunks)),
                pct,
            )
        segment_note = "\n(This is segment %d of %d. Extract minutes for this part only.)\n\n" % (
            i + 1,
            len(chunks),
        )
        prompt = prompt_prefix + context_block + segment_note + "TRANSCRIPT:\n" + chunk
        if getattr(settings, "log_llm_prompt", False):
            logger.info("Ollama prompt segment %d/%d (first 2000 chars):\n%s", i + 1, len(chunks), prompt[:2000])
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
    """Resolve template: meeting override, then project default. Refreshes from DB to get latest."""
    db.refresh(meeting)
    if meeting.template_id:
        t = db.query(Template).filter(Template.id == meeting.template_id).first()
        if t:
            db.refresh(t)
            return t
    if meeting.project_id:
        project = db.query(Project).filter(Project.id == meeting.project_id).first()
        if project and project.default_template_id:
            t = db.query(Template).filter(Template.id == project.default_template_id).first()
            if t:
                db.refresh(t)
                return t
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
        format_spec_markdown = getattr(template, "format_spec_markdown", None) if template else None
        format_spec_markdown = (format_spec_markdown or "").strip() or None

        logger.info(
            "Format meeting %s: template_id=%s template_name=%s format_spec_len=%s",
            meeting_id,
            meeting.template_id,
            template.name if template else None,
            len(format_spec_markdown or ""),
        )

        try:
            set_progress(meeting_id, "Generating minutes with Ollama...", 85)
            try:
                content = format_transcript_with_ollama(
                    transcript.raw_text,
                    prompt_suffix=prompt_suffix,
                    template_sample=template_sample,
                    format_spec_markdown=format_spec_markdown,
                    meeting_id=meeting_id,
                    summary_context=getattr(meeting, "summary_context", None) or None,
                )
                if content.get("_markdown"):
                    markdown = content["_markdown"]
                    formatted_content = {"markdown_only": True}
                    if content.get("_empty_response"):
                        meeting.error_message = (
                            "Ollama returned no text. Run: ollama run qwen3.5 (then Re-format)."
                        )
                else:
                    content = _sanitize_llm_content(content, transcript.raw_text)
                    markdown = _to_markdown(content, structure=structure)
                    formatted_content = content
                model_used = settings.ollama_model
            except Exception as e:
                logger.warning("Ollama unavailable (%s), using fallback minutes", e)
                content = _fallback_content(transcript.raw_text)
                markdown = _to_markdown(content, structure=structure)
                formatted_content = content
                model_used = "fallback (Ollama unavailable)"

            minute = Minute(
                meeting_id=meeting_id,
                formatted_content=formatted_content,
                template_id=template.id if template else None,
                model_used=model_used,
                markdown=markdown,
            )
            db.add(minute)

            meeting.status = MeetingStatus.FORMATTED
            if not content.get("_empty_response"):
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
