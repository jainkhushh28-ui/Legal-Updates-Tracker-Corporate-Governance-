"""Optional automatic, source-bound drafting using Gemini's structured output.

The model gets only the captured primary-source text. It must attach a verbatim
quote from that text to every public-facing field. Validation rejects the entire
draft when any quote is absent, so a failed or uncertain draft is not published.
"""
from __future__ import annotations

import json
import os
import re
import time


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _schema() -> dict:
    citation = {"type": "array", "items": {"type": "string"}, "minItems": 1}
    properties = {
        "title": {"type": "string"}, "update_type": {"type": "string"},
        "law_area": {"type": "string"}, "applicability": {"type": "string"},
        "description": {"type": "string"}, "summary": {"type": "string"},
        "takeaway": {"type": "string"}, "effective_date": {"type": "string"},
        "title_evidence": citation, "update_type_evidence": citation,
        "applicability_evidence": citation, "description_evidence": citation,
        "summary_evidence": citation, "takeaway_evidence": citation,
        "effective_date_evidence": citation,
    }
    return {"type": "object", "properties": properties, "required": list(properties)}


def _validate(draft: dict, source_text: str, logic: dict) -> tuple[bool, str]:
    source = _normalise(source_text)
    fields = ("title", "update_type", "applicability", "description", "summary", "takeaway", "effective_date")
    for field in fields:
        value = str(draft.get(field, "")).strip()
        evidence = draft.get(f"{field}_evidence", [])
        if not value or not isinstance(evidence, list) or not evidence:
            return False, f"missing {field} or its evidence"
        if any(_normalise(quote) not in source for quote in evidence):
            return False, f"{field} evidence is not verbatim in source"
    if draft["update_type"] not in logic["update_types"]:
        return False, "update type is outside approved categories"
    if draft["effective_date"] != "Not stated in source" and not any(
        _normalise(draft["effective_date"]) in _normalise(quote)
        for quote in draft["effective_date_evidence"]
    ):
        return False, "effective date is not present in its evidence"
    return True, ""


# Free-tier Gemini quota is 15 requests per minute for this model. Pacing calls
# at this interval keeps a normal run comfortably under that limit instead of
# bursting through it and crashing mid-run.
MIN_SECONDS_BETWEEN_CALLS = 4.5
_last_call_at = 0.0


def _wait_for_rate_limit() -> None:
    global _last_call_at
    elapsed = time.monotonic() - _last_call_at
    if elapsed < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
    _last_call_at = time.monotonic()


def generate_source_bound_draft(record: dict, source_text: str, logic: dict) -> dict | None:
    """Return a publishable draft, or None if no configured key / evidence failure.

    On a 429 (rate limit / quota) response this waits and retries a few times
    rather than raising, so one busy source cannot crash the whole collection
    run and lose every item already gathered before it.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    # Long annexures are less useful than the operative portion in a first MVP.
    # A full-document chunker can be added once source-specific adapters are tested.
    source_text = source_text[:60000]
    prompt = f"""You are a source-bound legal update extractor for India. You are not a legal adviser.
Return JSON only. Use ONLY the PRIMARY SOURCE TEXT below. Do not use background knowledge.
Every field requires one or more VERBATIM quotes from the source in its matching evidence array.
If a point is uncertain, omit the entire result by returning no useful draft; never guess.

Allowed update types: {json.dumps(logic['update_types'])}
Applicability mapping: {json.dumps(logic['applicability_mappings'])}
Writing rules: {json.dumps(logic['formats'])}

Authority: {record['regulatory_authority']}
Official index title: {record['title']}
PRIMARY SOURCE TEXT START
{source_text}
PRIMARY SOURCE TEXT END"""
    client = genai.Client(api_key=api_key)

    response = None
    max_attempts = 4
    for attempt in range(max_attempts):
        _wait_for_rate_limit()
        try:
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_schema(), temperature=0,
                ),
            )
            break
        except genai_errors.ClientError as exc:
            is_rate_limit = getattr(exc, "code", None) == 429
            if is_rate_limit and attempt < max_attempts - 1:
                # Free tier resets quickly; back off a bit longer each retry.
                time.sleep(35 + 10 * attempt)
                continue
            # Either a non-rate-limit error, or we've retried enough: skip this
            # item gracefully instead of crashing the whole collection run.
            return None

    if response is None:
        return None
    try:
        draft = json.loads(response.text)
    except (TypeError, json.JSONDecodeError):
        return None
    ok, _reason = _validate(draft, source_text, logic)
    if not ok:
        return None
    return draft
