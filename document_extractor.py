"""Download exact official documents and extract auditable text.

The source file is retained locally by hash for audit/review. This module does not
summarise or interpret a document: it is the evidence layer for the analysis step.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DOCUMENT_DIR = ROOT / "data" / "source_documents"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
# Tags/regions that are site chrome, not the document itself. Almost every
# Indian government site repeats a "Recruitment / RTI / Tender / Annual
# Report" style footer or nav menu on every single page — if that text is
# left in, it falsely trips the editorial exclusion filter on every item
# regardless of what the actual circular says.
BOILERPLATE_TAGS = ("nav", "header", "footer", "script", "style", "noscript", "aside")
BOILERPLATE_HINTS = ("nav", "menu", "footer", "header", "breadcrumb", "sidebar", "cookie")


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(BOILERPLATE_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        identifiers = " ".join([tag.get("id", ""), *(tag.get("class") or [])]).lower()
        if any(hint in identifiers for hint in BOILERPLATE_HINTS):
            tag.decompose()


@dataclass
class SourceDocument:
    url: str
    content_type: str
    sha256: str
    extracted_text: str
    local_path: str


def _safe_extension(content_type: str, url: str) -> str:
    if "pdf" in content_type.lower() or urlparse(url).path.lower().endswith(".pdf"):
        return ".pdf"
    return ".html"


def extract_document(url: str) -> SourceDocument:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=45)
    response.raise_for_status()
    payload = response.content
    content_type = response.headers.get("Content-Type", "")
    digest = hashlib.sha256(payload).hexdigest()
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    local_file = DOCUMENT_DIR / f"{digest}{_safe_extension(content_type, url)}"
    if not local_file.exists():
        local_file.write_bytes(payload)

    is_pdf = "pdf" in content_type.lower() or local_file.suffix == ".pdf"
    if is_pdf:
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)
    else:
        soup = BeautifulSoup(payload, "html.parser")
        _strip_boilerplate(soup)
        text = soup.get_text(" ", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return SourceDocument(url, content_type, digest, text, str(local_file.relative_to(ROOT)))


def evidence_snippets(text: str, terms: list[str], max_snippets: int = 4) -> list[str]:
    """Return verbatim nearby source text—never model-created quotations."""
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    matches = [s.strip() for s in sentences if any(term.lower() in s.lower() for term in terms)]
    return matches[:max_snippets]
