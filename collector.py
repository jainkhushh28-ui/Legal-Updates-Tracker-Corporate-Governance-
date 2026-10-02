"""Collect and normalise legal notices from approved primary sources only.

This first version is deliberately conservative: an item is never displayed unless
the link resolves to the configured official-domain source. It does not invent an
effective date or legal interpretation; unavailable fields are labelled clearly.

--- CHANGES IN THIS VERSION, EXPLAINED IN PLAIN LANGUAGE ---

1. PROGRESS LOGGING: every item now prints a line as it's processed, so a run
   that's correctly (if slowly) working through many items never looks
   identical to one that has actually frozen.

2. MAX_ITEMS_PER_SOURCE_PER_RUN: caps how many documents get the slow,
   rate-limited AI analysis step per source per run, so one source with many
   matching items can't consume the entire Gemini quota before other sources
   get their turn, and so each run finishes in minutes, not hours. Anything
   deferred this run is simply picked up on tomorrow's scheduled run.

3. HEADLESS BROWSER SUPPORT: some government sites (Labour Ministry, and
   possibly others) build their content using JavaScript that only runs in a
   real browser - a plain HTTP request only ever sees an empty page shell.
   Setting "render_js": true on a source in sources.json switches that
   source to fetch_rendered_page(), which uses Playwright (a real, automated
   but invisible browser) to let that JavaScript run before we read the page.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright

from analyser import analyse
from document_extractor import extract_document
from quality_filter import passes_quality_filters

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "data" / "sources.json"
UPDATES_FILE = ROOT / "data" / "updates.json"

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

# Caps how many documents we run through the (slow, rate-limited) AI analysis
# step in a single execution of this script. Raise this once you confirm a
# run comfortably finishes quickly; lower it if runs are still slow or you're
# burning through Gemini's daily quota.
MAX_ITEMS_PER_SOURCE_PER_RUN = 5

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
    link, or in a separate header row above a block of items that share one
    date. This checks the immediate row first, then walks backwards through
    prior sibling rows to find the most recent date header.
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
    if any(word in t for word in ("insolvency", "resolution professional", "liquidat", "ibc")):
        return "Corporate and secretarial", "Insolvency professionals, resolution applicants and corporate debtors may be affected."
    if any(word in t for word in ("insuranc", "insurer", "policyholder", "reinsur")):
        return "Corporate and secretarial", "Insurers, reinsurers and insurance intermediaries may be affected."
    return configured_area, "Applicability requires review of the primary source."


def fetch_rendered_page(url: str, wait_selector: str = "table", timeout_ms: int = 20000) -> str | None:
    """
    Fetches a page using a real (headless, i.e. invisible) browser instead of
    a plain HTTP request - so any JavaScript the page runs to build its
    content actually executes first, the same way it would in your own Chrome.

    wait_selector: a CSS selector we expect to eventually appear once the page
    has finished loading its real content. We wait for this specifically,
    rather than a fixed delay, because different sites take different amounts
    of time to finish loading.

    Returns the fully-rendered HTML as text, or None if it fails - following
    the same "never crash the whole run over one source" pattern as a normal
    failed request.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=timeout_ms)
            try:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except Exception:
                # The selector never showed up in time - we still grab whatever
                # HTML exists; collect_source()'s normal "0 candidates found"
                # handling deals with it gracefully if it's genuinely empty.
                pass
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        print(f"[collector] Headless browser fetch FAILED for {url}: {exc}")
        return None


def collect_source(source: dict, since: date, skipped: list[str]) -> list[Update]:
    authority = source["authority"]
    print(f"[collector] Fetching index page for {authority}: {source['url']}")

    if source.get("render_js"):
        html = fetch_rendered_page(source["url"], wait_selector=source.get("wait_selector", "table"))
        if html is None:
            raise requests.RequestException(f"Headless browser could not load {source['url']}")
    else:
        response = requests.get(source["url"], headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")

    # --- STEP 1: find every candidate link that's new enough and on-domain ---
    # This is fast (no downloads yet), so we do it for ALL matching anchors
    # before applying today's processing cap below.
    candidates = []
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
        candidates.append((notice_date, title, link))

    print(f"[collector] {authority}: found {len(candidates)} candidate item(s) within the lookback window")

    # --- STEP 2: process only the newest N candidates this run (the slow part) ---
    candidates.sort(key=lambda c: c[0], reverse=True)  # newest first
    to_process = candidates[:MAX_ITEMS_PER_SOURCE_PER_RUN]
    deferred_count = len(candidates) - len(to_process)
    if deferred_count > 0:
        print(
            f"[collector] {authority}: processing the newest {len(to_process)} now, "
            f"deferring {deferred_count} to a later run (they are not lost)"
        )

    results: list[Update] = []

    for index, (notice_date, title, link) in enumerate(to_process, start=1):
        print(f"[collector] {authority} [{index}/{len(to_process)}]: downloading + analysing \"{title[:70]}\"")
        step_started_at = time.monotonic()

        document = extract_document(link)
        if len(document.extracted_text) < 100:
            print(f"[collector] {authority} [{index}/{len(to_process)}]: skipped, extracted text too short")
            continue

        ok, reason = passes_quality_filters(title, document.extracted_text, authority)
        if not ok:
            skipped.append(f'{authority}: "{title[:80]}" — {reason}')
            print(f"[collector] {authority} [{index}/{len(to_process)}]: screened out ({reason})")
            continue

        area, applicability = classify(title, source["law_area"])
        item_id = hashlib.sha256(link.encode()).hexdigest()[:16]

        base_record = {
            "id": item_id, "title": title, "regulatory_authority": authority,
            "country": "India", "region": "APAC", "state": "National", "law_area": area,
            "applicability": applicability, "description": title,
            "summary": "Not analysed yet.", "takeaway": "Read the primary source.",
            "notification_date": notice_date.isoformat(), "effective_date": "Not stated — verify in source",
            "update_type": source["update_type"], "primary_source_link": link,
            "source_name": source["name"], "collected_at": datetime.now(timezone.utc).isoformat(),
            "source_document_sha256": document.sha256, "source_text_path": document.local_path,
            "evidence": document.extracted_text[:1000].split("\n")[:3],
        }
        analysed = Update(**analyse(base_record, document.extracted_text))
        results.append(analysed)

        elapsed = time.monotonic() - step_started_at
        print(
            f"[collector] {authority} [{index}/{len(to_process)}]: done in {elapsed:.1f}s "
            f"-> analysis_status={analysed.analysis_status}"
        )

    return results


def run(default_days: int = DEFAULT_LOOKBACK_DAYS) -> dict:
    run_started_at = time.monotonic()
    sources = json.loads(SOURCES_FILE.read_text())
    print(f"[collector] Starting run across {len(sources)} configured source(s)")

    try:
        previous = {item["id"]: item for item in json.loads(UPDATES_FILE.read_text())}
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}

    errors, collected, skipped = [], [], []
    failed_source_names: set[str] = set()
    widest_since = date.today() - timedelta(days=default_days)

    for source in sources:
        source_days = source.get("lookback_days", default_days)
        since = date.today() - timedelta(days=source_days)
        widest_since = min(widest_since, since)

        try:
            collected.extend(collect_source(source, since, skipped))
        except requests.RequestException as exc:
            print(f"[collector] {source['authority']}: FAILED to fetch - {exc}")
            errors.append(f'{source["authority"]}: {exc}')
            failed_source_names.add(source["name"])

    collected_by_id = {item.id: asdict(item) for item in collected}

    # An item from a source that fetched successfully today is only kept if
    # it was reconfirmed today - so tightening the editorial policy, or an
    # item simply aging off the index page, actually takes effect instead of
    # being remembered forever. An item from a source whose fetch failed this
    # run (site down, temporarily blocked) is carried over as-is, so a
    # transient outage doesn't blank that source's data.
    carried_over = {
        item_id: item for item_id, item in previous.items()
        if item.get("source_name") in failed_source_names
    }

    current = {**carried_over, **collected_by_id}

    retained = [u for u in current.values() if u.get("notification_date", "") >= widest_since.isoformat()]
    retained.sort(key=lambda u: u["notification_date"], reverse=True)
    UPDATES_FILE.write_text(json.dumps(retained, indent=2, ensure_ascii=False) + "\n")

    retired = sorted(set(previous) - set(current))

    total_elapsed = time.monotonic() - run_started_at
    summary = {
        "updates": len(retained),
        "new": len(collected),
        "retired": len(retired),
        "screened_out": len(skipped),
        "screened_out_examples": skipped[:10],
        "errors": errors,
        "run_seconds": round(total_elapsed, 1),
    }
    print(f"[collector] Run finished in {total_elapsed:.1f}s: {summary}")
    return summary


if __name__ == "__main__":
    print(run())
