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
USER_AGENT = "LegalUpdateTracker/0.1 (educational portfolio project)"


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
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
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
        # Imported only for PDFs so the dashboard and HTML-source tests remain
        # usable before dependencies are installed in a fresh environment.
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)
    else:
        text = BeautifulSoup(payload, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return SourceDocument(url, content_type, digest, text, str(local_file.relative_to(ROOT)))


def evidence_snippets(text: str, terms: list[str], max_snippets: int = 4) -> list[str]:
    """Return verbatim nearby source text—never model-created quotations."""
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    matches = [s.strip() for s in sentences if any(term.lower() in s.lower() for term in terms)]
    return matches[:max_snippets]
