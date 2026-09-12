"""Create evidence-bound draft records from extracted primary-source text.

No model call is made here.  Until the user provides reviewed output logic, every
document stays in `needs_rule_logic` and cannot become a published legal update.
"""
from __future__ import annotations

import json
from pathlib import Path

from document_extractor import evidence_snippets
from gemini_analyser import generate_source_bound_draft

ROOT = Path(__file__).parent
LOGIC_FILE = ROOT / "analysis_logic.json"


def analyse(record: dict, source_text: str) -> dict:
    logic = json.loads(LOGIC_FILE.read_text())
    automatic_draft = generate_source_bound_draft(record, source_text, logic)
    if automatic_draft:
        return record | {
            "analysis_status": "published",
            "title": automatic_draft["title"],
            "law_area": automatic_draft["law_area"],
            "applicability": automatic_draft["applicability"],
            "description": automatic_draft["description"],
            "summary": automatic_draft["summary"],
            "takeaway": automatic_draft["takeaway"],
            "effective_date": automatic_draft["effective_date"],
            "update_type": automatic_draft["update_type"],
            "field_evidence": {
                field: automatic_draft[f"{field}_evidence"]
                for field in ("title", "update_type", "applicability", "description", "summary", "takeaway", "effective_date")
            },
        }
    base = {
        "analysis_status": "withheld_no_validated_draft",
        "description": "Source document captured; no validated automatic draft was produced.",
        "summary": "Not generated.",
        "takeaway": "Read the exact primary source.",
        "field_evidence": {},
    }
    for rule in logic.get("rules", []):
        triggers = rule.get("trigger_words", [])
        if not triggers or not all(word.lower() in source_text.lower() for word in triggers):
            continue
        snippets = evidence_snippets(source_text, triggers)
        if not snippets:
            continue
        # Templates are supplied and approved by the legal professional, not invented.
        base.update({
            "analysis_status": "draft_requires_human_approval",
            "law_area": rule["law_area"],
            "applicability": rule["applicability_template"],
            "description": rule["description_template"],
            "summary": rule["summary_template"],
            "takeaway": rule["takeaway_template"],
            "field_evidence": {
                "applicability": snippets,
                "description": snippets,
                "summary": snippets,
                "takeaway": snippets,
            },
        })
        break
    return record | base
