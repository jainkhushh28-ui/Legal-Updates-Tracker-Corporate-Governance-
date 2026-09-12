"""Editorial capture policy for what counts as a publishable legal update.

Encodes the five-step decision process supplied for this project:
1. Section/tab scope   -> enforced by which source pages are configured (data/sources.json)
2. Entity-generality    -> exclude documents addressed to a single named respondent
3. Obligation language  -> exclude purely descriptive/statistical/celebratory text
4. Inclusion keywords   -> must relate to a tracked compliance topic
5. Exclusion override   -> even a keyword match is discarded if it matches a known
                           non-substantive category (speeches, press releases, etc.)

This module only decides whether to keep looking at an item. It never drafts or
rewrites text — that stays the job of gemini_analyser.py, bound to verbatim
source quotes.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Step: obligation language. An item must contain operative/binding language,
# not just be about a topic in the abstract (news, statistics, commentary).
# ---------------------------------------------------------------------------
OBLIGATION_PATTERN = re.compile(
    r"\b(shall|is required to|are required to|mandat(?:ed|ory)|amend(?:ed|ment)|"
    r"insert(?:ed)?|substitut(?:ed)?|with effect from|w\.e\.f\.?|"
    r"due date (?:extended|revised)|last date (?:extended|revised)|"
    r"threshold revised|revised threshold|extension of time|"
    r"notified that|hereby directs?|in supersession of)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Step: inclusion keywords (Section A). Any one match is enough to proceed.
# Grouped only for readability; matching is a flat search across all of them.
# ---------------------------------------------------------------------------
INCLUSION_KEYWORDS = [
    # A1 — Corporate law / company secretarial
    "board meeting", "general meeting", "agm", "egm", "postal ballot",
    "video conferencing for meetings", "independent director", "women director",
    "whole-time director", "additional director", "alternate director",
    "resignation of director", "removal of director", "din", "dir-3", "kyc",
    "disqualification of director", "equity share", "preference share",
    "sweat equity", "esop", "private placement", "rights issue", "bonus issue",
    "buyback", "reduction of capital", "transfer of shares", "transmission of shares",
    "dematerialisation", "dematerialization", "incorporation", "conversion of company",
    "strike off", "winding up", "nclt", "secretarial standard", "ss-1", "ss-2",
    "secretarial audit", "annual return", "mgt-7", "financial statement",
    "board's report", "board report", "auditor's report", "auditor rotation",
    "related party transaction", "key managerial personnel", "kmp",
    "company secretary", "managerial remuneration", "csr",
    "corporate social responsibility", "acceptance of deposits", "charges",
    "registrar of companies", "compounding of offences", "adjudication framework",
    "penalty", "additional fees", "relaxation of fees", "mca21", "xbrl",

    # A2 — Securities law / stock exchanges
    "lodr", "icdr", "consultation paper", "master circular", "issue of securities",
    "ipo", "fpo", "qip", "preferential issue", "offer for sale", "delisting",
    "takeover code", "sast", "insider trading", "upsi", "trading window",
    "brsr", "business responsibility report", "corporate governance report",
    "regulation 30", "material event", "record date", "scheme of arrangement",
    "merger", "demerger", "depositories", "beneficial ownership", "sbo",
    "credit rating", "debenture trustee", "commercial paper", "ceo certification",
    "cfo certification", "structured digital database",

    # A3 — FEMA / RBI
    "fema", "master direction", "fla return", "flair", "overseas direct investment",
    "odi", "external commercial borrowing", "ecb", "foreign direct investment",
    "fdi", "fc-gpr", "fc-trs", "downstream investment",
    "liberalised remittance scheme", "lrs", "compounding under fema",
    "annual performance report", "single master form", "nbfc regulatory framework",

    # A4 — Employment / labour law
    "minimum wages", "code on wages", "payment of bonus", "payment of gratuity",
    "provident fund", "epf", "interest rate", "employees' state insurance", "esi",
    "social security code", "maternity benefit", "statutory holiday",
    "shops & establishment", "shops and establishment", "working hours", "overtime",
    "industrial relations code", "industrial dispute", "standing orders",
    "trade union", "layoff", "retrenchment", "occupational safety",
    "osh code", "posh", "sexual harassment", "contract labour", "migrant worker",
    "apprenticeship", "labour welfare fund", "professional tax", "gratuity trust",
    "statutory bonus", "shram suvidha",

    # A5 — Cross-cutting tax (secondary relevance to CS function)
    "gst", "tds", "form 15ca", "form 15cb", "transfer pricing", "stamp duty",
]

# ---------------------------------------------------------------------------
# Step: entity-specific / case-specific exclusions. These apply across all
# authorities: a document addressed to one named respondent is a case action,
# not a rule of general applicability.
# ---------------------------------------------------------------------------
ENTITY_SPECIFIC_PATTERNS = [
    "in the matter of", "show cause notice", "adjudication order",
    "settlement order", "consent order", "debarment order", "wtm order",
    "whole time member order", "appeal before sat", "penalty order",
    "licence cancellation", "license cancellation", "cancellation of licence",
    "cancellation of license",
]

# ---------------------------------------------------------------------------
# Step: exclusion override (Section B). Even a keyword match is discarded if
# the item falls into one of these non-substantive categories.
# ---------------------------------------------------------------------------
GENERIC_EXCLUSIONS = [
    "press release", "speech by", "address by", "book launch", "felicitat",
    "anniversary", "annual report", "recruitment", "vacancy", "tender notice",
    "rti disclosure", "investor awareness program", "investor awareness workshop",
    "webinar announcement", "public auction", "caution alert", "grievance redressal camp",
    "digital life certificate camp", "conference", "mou signed", "workshop on",
]

AUTHORITY_EXCLUSIONS: dict[str, list[str]] = {
    "SEBI": [
        "annual report", "financial statement of sebi",
    ],
    "RBI": [
        "monetary policy statement", "press briefing", "speech by governor",
        "speech by deputy governor", "financial stability report",
        "museum", "numismatics", "coin", "recruitment", "tender",
        "working paper", "occasional paper", "sectoral credit deployment",
        "reference rate for", "wss ", "weekly statistical supplement",
    ],
    "MCA": [
        "regional director", "official liquidator", "ease of doing business ranking",
        "fake website", "fraudulent website",
    ],
    "Ministry of Labour & Employment": [
        "speech by minister", "yojana", "felicitation", "international conference",
        "recruitment", "digital life certificate",
    ],
    "NSE": [
        "trading holiday", "settlement statistics", "market data bulletin",
        "index launch", "investor awareness", "trading suspension",
    ],
    "BSE": [
        "trading holiday", "settlement statistics", "market data bulletin",
        "index launch", "investor awareness", "trading suspension",
    ],
}


def _contains_any(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern in text:
            return pattern
    return None


def passes_quality_filters(title: str, body_text: str, authority: str) -> tuple[bool, str]:
    """Decide whether an item is worth analysing and possibly publishing.

    Returns (True, "included") or (False, reason). Matching is deliberately
    generous with context: it looks at the title plus the first slice of the
    extracted document text, since obligation language and effective dates
    usually live in the body, not the index-page title.
    """
    text = f"{title} {body_text[:4000]}".lower()

    hit = _contains_any(text, ENTITY_SPECIFIC_PATTERNS)
    if hit:
        return False, f"case-specific action, not a general rule (matched '{hit}')"

    # MCA21 portal patch notes are excluded unless they change an actual form
    # or filing process — a narrow, explicitly-stated carve-out.
    if authority == "MCA" and "mca21" in text and "portal" in text:
        if not any(k in text for k in ("filing process", "e-form", " form ")):
            return False, "MCA21 portal/UI note without a stated filing-process change"

    hit = _contains_any(text, GENERIC_EXCLUSIONS)
    if hit:
        return False, f"non-substantive category (matched '{hit}')"

    hit = _contains_any(text, AUTHORITY_EXCLUSIONS.get(authority, []))
    if hit:
        return False, f"excluded category for {authority} (matched '{hit}')"

    if not OBLIGATION_PATTERN.search(text):
        return False, "no operative/obligation language found"

    hit = _contains_any(text, INCLUSION_KEYWORDS)
    if not hit:
        return False, "no tracked compliance topic matched"

    return True, f"included (matched '{hit}')"
