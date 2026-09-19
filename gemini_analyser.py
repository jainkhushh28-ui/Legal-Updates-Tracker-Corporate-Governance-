"""Optional automatic, source-bound drafting using Gemini's structured output.

The model gets only the captured primary-source text. It must attach a verbatim
quote from that text to every public-facing field. Validation rejects the entire
draft when any quote is absent, so a failed or uncertain draft is not published.

--- CHANGES IN THIS VERSION (explained in plain language) ---

1. VISIBLE FAILURE REASONS: previously, ANY problem (a real API error, a quota
   limit, or the model's answer failing our verbatim-quote check) all silently
   returned None, with zero explanation. That made it impossible to tell "Gemini
   is out of quota" apart from "the model gave a bad answer" apart from "our
   validation is too strict." Every failure now prints exactly which of those
   three things happened, and validation failures now print WHICH field failed
   and why - so we can actually see what's going wrong instead of guessing.

2. RICHER PROMPT: the previous prompt asked for a summary/applicability/
   takeaway but didn't specify what "good" looks like, so short, generic
   answers were technically valid. The new prompt spells out exactly what
   each field must contain (see the "Writing rules" section below) - e.g.
   the takeaway must now be phrased as a concrete action, not just a
   restatement of the update.
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
    """
    Returns (True, "") if the draft is publishable, or (False, reason) if not.

    CHANGED: the reason is now specific enough to act on, e.g. "summary
    evidence is not verbatim in source" tells you exactly which field and
    exactly why - instead of every failure looking the same from outside.
    """
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
        return False, f"update type '{draft['update_type']}' is outside approved categories {logic['update_types']}"
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
    title_preview = record.get("title", "?")[:60]
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"[gemini_analyser] \"{title_preview}\": no GEMINI_API_KEY set - skipping AI analysis entirely")
        return None
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    # Long annexures are less useful than the operative portion in a first MVP.
    # A full-document chunker can be added once source-specific adapters are tested.
    source_text = source_text[:60000]

    # WRITING RULES: spelled out explicitly so the model can't satisfy the
    # schema with short, generic answers. Each rule targets one of the
    # complaints about vague summaries/applicability/takeaways.
    writing_rules = {
        "summary": (
            "3-5 sentences. Must cover, in this order: (1) WHAT changed or was "
            "clarified/introduced, in concrete terms (name the specific rule, "
            "form, threshold, or process affected - not just 'a change was made'); "
            "(2) WHY the regulator issued this (the stated reason, problem being "
            "solved, or prior circular being amended, if the source states one); "
            "(3) the practical EFFECT on a real compliance workflow (what will "
            "look different in practice after this takes effect)."
        ),
        "applicability": (
            "Name the SPECIFIC category of entity this applies to, as precisely "
            "as the source allows - e.g. 'Listed companies with paid-up equity "
            "share capital exceeding Rs 10 crore' rather than just 'companies'; "
            "'Scheduled commercial banks excluding RRBs' rather than just "
            "'banks'. If the source states a threshold, timeline-based scope, "
            "or an exemption, include it. If truly no narrowing detail exists "
            "in the source, say so explicitly rather than writing a vague catch-all."
        ),
        "takeaway": (
            "A specific, actionable instruction for a compliance officer or "
            "employer, phrased as what they should DO or CHECK - e.g. 'Update "
            "the KYC verification checklist to include the revised document "
            "list before the next onboarding cycle' rather than 'Ensure "
            "compliance with the new rule.' If the source specifies a deadline "
            "or filing requirement, the takeaway must name it."
        ),
    }

    prompt = f"""You are a source-bound legal update extractor for India. You are not a legal adviser.
Return JSON only. Use ONLY the PRIMARY SOURCE TEXT below. Do not use background knowledge.
Every field requires one or more VERBATIM quotes from the source in its matching evidence array.
If a point is uncertain, omit the entire result by returning no useful draft; never guess.

Allowed update types: {json.dumps(logic['update_types'])}
Applicability mapping: {json.dumps(logic['applicability_mappings'])}
General writing rules: {json.dumps(logic['formats'])}

Additional, more specific writing requirements for these three fields:
{json.dumps(writing_rules, indent=2)}

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
            print(
                f"[gemini_analyser] \"{title_preview}\": Gemini API error on attempt "
                f"{attempt + 1}/{max_attempts} - code={getattr(exc, 'code', '?')}, "
                f"rate_limited={is_rate_limit}, message={str(exc)[:200]}"
            )
            if is_rate_limit and attempt < max_attempts - 1:
                # Free tier resets quickly; back off a bit longer each retry.
                wait_seconds = 35 + 10 * attempt
                print(f"[gemini_analyser] \"{title_preview}\": waiting {wait_seconds}s before retrying")
                time.sleep(wait_seconds)
                continue
            # Either a non-rate-limit error, or we've retried enough: skip this
            # item gracefully instead of crashing the whole collection run.
            print(f"[gemini_analyser] \"{title_preview}\": giving up after this error, item will be withheld")
            return None

    if response is None:
        print(f"[gemini_analyser] \"{title_preview}\": no response object returned, item will be withheld")
        return None
    try:
        draft = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        print(f"[gemini_analyser] \"{title_preview}\": could not parse model response as JSON - {exc}")
        print(f"[gemini_analyser] Raw response was: {str(response.text)[:300]}")
        return None
    ok, reason = _validate(draft, source_text, logic)
    if not ok:
        print(f"[gemini_analyser] \"{title_preview}\": draft REJECTED - {reason}")
        return None
    print(f"[gemini_analyser] \"{title_preview}\": draft PASSED validation")
    return draft
