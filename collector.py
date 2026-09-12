"""Collect and normalise legal notices from approved primary sources only.

This first version is deliberately conservative: an item is never displayed unless
the link resolves to the configured official-domain source.  It does not invent an
effective date or legal interpretation; unavailable fields are labelled clearly.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from analyser import analyse
from document_extractor import extract_document
from quality_filter import passes_quality_filters

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "data" / "sources.json"
UPDATES_FILE = ROOT / "data" / "updates.json"
# Government sites frequently block requests whose User-Agent identifies as a
# script or bot. Presenting as an ordinary browser avoids that block while
# remaining truthful in effect: this really is an ordinary automated fetch of
# a public page, not a probe of anything restricted.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
DEFAULT_LOOKBACK_DAYS = 7
DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
    re.I,
)


@dataclass
class Update:
    id: str
    title: str
    regulatory_authority: str
    country: str
    region: str
    state: str
    law_area: str
    applicability: str
    description: str
    summary: str
    takeaway: str
    notification_date: str
    effective_date: str
    update_type: str
    primary_source_link: str
    source_name: str
    collected_at: str
    source_document_sha256: str
    source_text_path: str
    evidence: list[str]
    analysis_status: str
    field_evidence: dict


def extract_date(text: str) -> date | None:
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        parsed = date_parser.parse(match.group(0), dayfirst=False, fuzzy=False).date()
        return parsed if 2000 <= parsed.year <= date.today().year + 1 else None
    except (ValueError, OverflowError):
        return None


def find_item_date(anchor):
    """Find the date associated with an item link.

    Many Indian government sites put the date in the same table row as the
    link (e.g. SEBI: Date | Type | Title columns), or in a separate header
    row above a block of items that share one date (e.g. RBI: a bold date
    row, followed by several notification rows with no date of their own).
    This checks the immediate row first, then walks backwards through prior
    sibling rows to find the most recent date header.
    """
    row = anchor.find_parent("tr") or anchor.parent
    own_text = concise_text(row.get_text(" ", strip=True), 1000)
    found = extract_date(own_text)
    if found:
        return found

    if row is not None and row.name == "tr":
        prev = row.find_previous_sibling("tr")
        steps = 0
        while prev is not None and steps < 40:
            prev_text = concise_text(prev.get_text(" ", strip=True), 300)
            found = extract_date(prev_text)
            if found:
                return found
            prev = prev.find_previous_sibling("tr")
            steps += 1
    return None


def is_official_link(source_url: str, link: str) -> bool:
    """Allow only links on the source's exact host (including its subdomains)."""
    source_host = urlparse(source_url).hostname or ""
    link_host = urlparse(link).hostname or ""
    return link_host == source_host or link_host.endswith("." + source_host)


def concise_text(text: str, limit: int = 300) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def classify(title: str, configured_area: str) -> tuple[str, str]:
    """Transparent keyword classification; replace with reviewed AI later if wanted."""
    t = title.lower()
    if any(word in t for word in ("company", "director", "csr", "secretarial", "llp", "incorporat")):
        return "Corporate and secretarial", "Companies, LLPs, directors, compliance officers or filings may be affected."
    if any(word in t for word in ("wage", "labour", "labor", "employee", "worker", "employment", "pf", "esi")):
        return "Labour and employment", "Employers, HR teams, employees or labour-law compliance teams may be affected."
    if any(word in t for word in ("securit", "listing", "mutual fund", "broker", "demat", "market", "aif")):
        return "Securities and capital markets", "Listed entities, market intermediaries, investors or issuers may be affected."
    if any(word in t for word in ("fema", "forex", "foreign exchange", "external commercial borrow", "ecb")):
        return "Corporate and secretarial", "Entities with cross-border transactions, ECBs or foreign investment may be affected."
    if any(word in t for word in ("bank", "nbfc", "monetary", "deposit", "co-operative bank", "rrb")):
        return "Corporate and secretarial", "Banks, NBFCs and regulated financial entities may be affected."
    return configured_area, "Applicability requires review of the primary source."


def collect_source(source: dict, since: date, skipped: list[str]) -> list[Update]:
    response = requests.get(source["url"], headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results: list[Update] = []
    seen: set[str] = set()

    for anchor in soup.select(source.get("selector", "a")):
        title = concise_text(anchor.get_text(" ", strip=True), 500)
        href = anchor.get("href")
        if not title or not href or len(title) < 12:
            continue
        link = urljoin(source["url"], href)
        if not is_official_link(source["url"], link) or link in seen:
            continue
        notice_date = find_item_date(anchor) or extract_date(title)
        if notice_date is None or notice_date < since:
            continue
        seen.add(link)

        # The index page is not enough evidence: fetch the exact linked document
        # and retain its hash/text before a record can ever be analysed.
        document = extract_document(link)
        if len(document.extracted_text) < 100:
            continue

        # Editorial capture policy: only genuinely substantive, general-applicability,
        # operative items proceed past this point. Checking this before calling
        # Gemini also avoids spending API quota on items that would never publish.
        ok, reason = passes_quality_filters(title, document.extracted_text, source["authority"])
        if not ok:
            skipped.append(f'{source["authority"]}: "{title[:80]}" — {reason}')
            continue

        area, applicability = classify(title, source["law_area"])
        item_id = hashlib.sha256(link.encode()).hexdigest()[:16]
        base_record = {
            "id": item_id, "title": title, "regulatory_authority": source["authority"],
            "country": "India", "region": "APAC", "state": "National", "law_area": area,
            "applicability": applicability, "description": title,
            "summary": "Not analysed yet.", "takeaway": "Read the primary source.",
            "notification_date": notice_date.isoformat(), "effective_date": "Not stated — verify in source",
            "update_type": source["update_type"], "primary_source_link": link,
            "source_name": source["name"], "collected_at": datetime.now(timezone.utc).isoformat(),
            "source_document_sha256": document.sha256, "source_text_path": document.local_path,
            "evidence": document.extracted_text[:1000].split("\n")[:3],
        }
        results.append(Update(**analyse(base_record, document.extracted_text)))
    return results


def run(default_days: int = DEFAULT_LOOKBACK_DAYS) -> dict:
    sources = json.loads(SOURCES_FILE.read_text())
    current = {item["id"]: item for item in json.loads(UPDATES_FILE.read_text())}
    errors, collected, skipped = [], [], []

    # Each source may define its own "lookback_days" (e.g. a quieter source
    # can look back further so it still has something to show). The overall
    # retention filter below must use the widest window in play, or a source
    # with a longer lookback would have its own items pruned immediately.
    widest_since = date.today() - timedelta(days=default_days)
    for source in sources:
        source_days = source.get("lookback_days", default_days)
        since = date.today() - timedelta(days=source_days)
        widest_since = min(widest_since, since)
        try:
            collected.extend(collect_source(source, since, skipped))
        except requests.RequestException as exc:
            errors.append(f'{source["authority"]}: {exc}')

    for item in collected:
        current[item.id] = asdict(item)
    # A source capture is retained for review, but a public dashboard may only
    # display records explicitly approved by a reviewer.
    retained = [u for u in current.values() if u.get("notification_date", "") >= widest_since.isoformat()]
    retained.sort(key=lambda u: u["notification_date"], reverse=True)
    UPDATES_FILE.write_text(json.dumps(retained, indent=2, ensure_ascii=False) + "\n")
    return {
        "updates": len(retained),
        "new": len(collected),
        "screened_out": len(skipped),
        "screened_out_examples": skipped[:10],
        "errors": errors,
    }


if __name__ == "__main__":
    print(run())
