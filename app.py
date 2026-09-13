import json
from datetime import date, timedelta
from pathlib import Path

from dateutil import parser as date_parser
import streamlit as st

st.set_page_config(page_title="Regulatory Intelligence Dashboard", page_icon="⚖", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "updates.json"

STAKEHOLDER_GROUPS = {
    "MCA": "Corporate & Secretarial",
    "RBI": "Corporate & Secretarial",
    "SEBI": "Securities & Listing",
    "NSE": "Securities & Listing",
    "BSE": "Securities & Listing",
    "Ministry of Labour & Employment": "Employment Law",
}
GROUP_ORDER = ["Corporate & Secretarial", "Securities & Listing", "Employment Law"]
GROUP_BLURB = {
    "Corporate & Secretarial": "MCA, RBI and FEMA updates for company secretaries and compliance teams.",
    "Securities & Listing": "SEBI, NSE and BSE updates for listed entities and market intermediaries.",
    "Employment Law": "Ministry of Labour & Employment updates for HR and employment-law teams.",
}
# Subtle, low-saturation tints — pattern-matching without shouting.
AUTHORITY_TINT = {
    "MCA": ("rgba(66,99,148,0.14)", "#3E5C88"),
    "RBI": ("rgba(122,92,163,0.14)", "#6E5497"),
    "SEBI": ("rgba(58,128,116,0.14)", "#37796C"),
    "NSE": ("rgba(66,140,92,0.14)", "#3E8259"),
    "BSE": ("rgba(163,127,58,0.14)", "#93752F"),
    "Ministry of Labour & Employment": ("rgba(163,84,74,0.14)", "#9B4F45"),
}
URGENCY_STYLE = {
    "urgent": {"color": "#9E5449", "tint": "rgba(158,84,73,0.14)", "label": "Action required"},
    "pending": {"color": "#96792A", "tint": "rgba(150,121,42,0.14)", "label": "Upcoming"},
    "review": {"color": "#3F7A68", "tint": "rgba(63,122,104,0.14)", "label": "For review"},
}
URGENT_WINDOW_DAYS = 14


def classify_urgency(effective_date_text: str) -> str:
    """Bucket an item by how soon it needs attention, using only the
    evidence-quoted effective_date already captured for that item."""
    if not effective_date_text or "not stated" in effective_date_text.lower():
        return "review"
    try:
        parsed = date_parser.parse(effective_date_text, fuzzy=True, dayfirst=False).date()
    except (ValueError, OverflowError, TypeError):
        return "review"
    if parsed <= date.today() + timedelta(days=URGENT_WINDOW_DAYS):
        return "urgent"
    return "pending"


st.markdown(
    """
    <style>
    :root {
        --glass-bg: rgba(255,255,255,0.55);
        --glass-bg-strong: rgba(255,255,255,0.68);
        --glass-border: rgba(255,255,255,0.55);
        --ink: #2B2E36;
        --muted: #6B6E76;
    }
    html, body, [class*="css"] { font-family: Arial, Helvetica, sans-serif; }

    .stApp {
        background: linear-gradient(160deg, #EAF0F6 0%, #F1ECF6 45%, #EAF3EE 100%);
        background-attachment: fixed;
    }
    .block-container { padding-top: 0; max-width: 1040px; }

    /* ---- Sticky glass header ---- */
    .glass-header {
        position: sticky; top: 0; z-index: 999;
        margin: 0 -1rem 1.1rem -1rem;
        padding: 1.3rem 1.6rem 1.1rem 1.6rem;
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border);
        border-top: none;
        box-shadow: 0 1px 2px rgba(31,41,55,0.04), 0 8px 24px rgba(31,41,55,0.08), 0 20px 40px rgba(31,41,55,0.05);
    }
    .brand-title {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 1.9rem; font-weight: 700; color: var(--ink); margin: 0;
    }
    .brand-kicker { font-size: 0.78rem; letter-spacing: 0.03em; color: var(--muted); margin-bottom: 0.15rem; }
    .brand-summary { color: var(--muted); font-size: 0.92rem; margin-top: 0.55rem; max-width: 760px; line-height: 1.5; }

    /* ---- Glass sidebar ---- */
    section[data-testid="stSidebar"] > div {
        background: rgba(255,255,255,0.45);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-right: 1px solid rgba(255,255,255,0.5);
    }

    /* ---- Glass metric cards ---- */
    .metric-row { display: flex; gap: 0.9rem; margin-bottom: 1.3rem; flex-wrap: wrap; }
    .metric-card {
        flex: 1; min-width: 150px;
        background: var(--glass-bg-strong);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border);
        border-radius: 14px;
        padding: 0.95rem 1.1rem;
        box-shadow: 0 1px 2px rgba(31,41,55,0.04), 0 10px 24px rgba(31,41,55,0.07);
    }
    .metric-num { font-family: Georgia, serif; font-size: 1.6rem; font-weight: 700; color: var(--ink); line-height: 1; }
    .metric-label { color: var(--muted); font-size: 0.8rem; margin-top: 0.3rem; }

    /* ---- Glass update cards ---- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--glass-bg-strong) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        box-shadow: 0 1px 2px rgba(31,41,55,0.03), 0 12px 28px rgba(31,41,55,0.07), 0 24px 48px rgba(31,41,55,0.04);
    }

    .tag-pill, .status-pill {
        display: inline-block; font-size: 0.72rem; font-weight: 600;
        padding: 0.16rem 0.6rem; border-radius: 999px; margin-right: 0.4rem;
    }
    .update-meta { color: var(--muted); font-size: 0.82rem; margin: 0.4rem 0 0.5rem 0; }
    .update-title {
        font-family: Georgia, serif; font-size: 1.05rem; font-weight: 700; color: var(--ink);
        margin: 0 0 0.6rem 0; line-height: 1.4;
    }
    .field-label { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.1rem; }
    .field-value { color: var(--ink); font-size: 0.9rem; margin-bottom: 0.55rem; }
    .quote-line {
        border-left: 2px solid rgba(107,110,118,0.3); padding-left: 0.6rem; margin: 0.2rem 0 0.5rem 0;
        font-style: italic; color: var(--muted); font-size: 0.86rem;
    }

    /* ---- Sticky glass footer ---- */
    .glass-footer {
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
        padding: 0.7rem 1.6rem;
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-top: 1px solid var(--glass-border);
        box-shadow: 0 -8px 24px rgba(31,41,55,0.06);
        text-align: center;
    }
    .glass-footer p { color: var(--muted); font-size: 0.78rem; margin: 0; }
    .footer-spacer { height: 3.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="glass-header">
        <div class="brand-kicker">INDIA · OFFICIAL SOURCES ONLY</div>
        <p class="brand-title">Regulatory Intelligence Dashboard</p>
        <p class="brand-summary">
            An evidence-bound legal updates intelligence platform tracking MCA, RBI, SEBI, NSE, BSE and the
            Ministry of Labour &amp; Employment. Every published update carries a verbatim quote from its
            primary source document — nothing is summarised from memory or guessed, and unverified drafts are
            never shown. Built for company secretaries, securities &amp; listing compliance teams and
            employment-law professionals who need one trustworthy place to track regulatory change.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    all_updates = json.loads(DATA_FILE.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    all_updates = []

all_updates = [u for u in all_updates if u.get("analysis_status") == "published"]

with st.sidebar:
    st.markdown("**Filters**")
    window_days = st.slider("Show updates from the last N days", min_value=7, max_value=45, value=30, step=1)
    search_term = st.text_input("Search title or summary", "")
    st.divider()
    st.caption("Country: India · Region: APAC")
    st.caption("National sources only in this prototype.")

cutoff = (date.today() - timedelta(days=window_days)).isoformat()
updates = [u for u in all_updates if u.get("notification_date", "") >= cutoff]
if search_term.strip():
    term = search_term.strip().lower()
    updates = [
        u for u in updates
        if term in u.get("title", "").lower() or term in u.get("summary", "").lower()
    ]
for u in updates:
    u["_group"] = STAKEHOLDER_GROUPS.get(u.get("regulatory_authority", ""), "Other")
    u["_urgency"] = classify_urgency(u.get("effective_date", ""))

metric_html = '<div class="metric-row">'
metric_html += f'<div class="metric-card"><div class="metric-num">{len(updates)}</div><div class="metric-label">Total updates</div></div>'
for key in ("urgent", "pending", "review"):
    count = sum(1 for u in updates if u["_urgency"] == key)
    style = URGENCY_STYLE[key]
    metric_html += (
        f'<div class="metric-card"><div class="metric-num" style="color:{style["color"]}">{count}</div>'
        f'<div class="metric-label">{style["label"]}</div></div>'
    )
metric_html += "</div>"
st.markdown(metric_html, unsafe_allow_html=True)

tabs = st.tabs([f"{g} ({sum(1 for u in updates if u['_group'] == g)})" for g in GROUP_ORDER])

for tab, group in zip(tabs, GROUP_ORDER):
    with tab:
        st.caption(GROUP_BLURB[group])
        group_updates = sorted(
            (u for u in updates if u["_group"] == group),
            key=lambda u: u.get("notification_date", ""),
            reverse=True,
        )
        if not group_updates:
            st.info(
                "No verified updates in this group within the selected window. "
                "Widen the day range in the sidebar, or check back after the next collection run."
            )
            continue

        authorities = sorted({u["regulatory_authority"] for u in group_updates})
        selected_authorities = st.multiselect(
            "Authority", authorities, default=authorities, key=f"auth_{group}", label_visibility="collapsed"
        )
        for update in group_updates:
            if update["regulatory_authority"] not in selected_authorities:
                continue
            tint_bg, tint_text = AUTHORITY_TINT.get(update["regulatory_authority"], ("rgba(107,110,118,0.14)", "#5B6169"))
            urgency = URGENCY_STYLE[update["_urgency"]]
            with st.container(border=True):
                st.markdown(
                    f'<span class="tag-pill" style="background:{tint_bg};color:{tint_text}">{update["regulatory_authority"]}</span>'
                    f'<span class="status-pill" style="background:{urgency["tint"]};color:{urgency["color"]}">{urgency["label"]}</span>'
                    f'<div class="update-meta">{update["update_type"]} · {update["notification_date"]}</div>'
                    f'<div class="update-title">{update["title"]}</div>',
                    unsafe_allow_html=True,
                )
                left, right = st.columns(2)
                with left:
                    st.markdown(f'<div class="field-label">Applicability</div><div class="field-value">{update["applicability"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="field-label">Effective date</div><div class="field-value">{update["effective_date"]}</div>', unsafe_allow_html=True)
                with right:
                    st.markdown(f'<div class="field-label">Summary</div><div class="field-value">{update["summary"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="field-label">Takeaway</div><div class="field-value">{update["takeaway"]}</div>', unsafe_allow_html=True)
                st.link_button("View original document", update["primary_source_link"])
                with st.expander("Source evidence used for this update"):
                    for field, quotes in update.get("field_evidence", {}).items():
                        st.markdown(f"**{field.replace('_', ' ').title()}**")
                        for quote in quotes:
                            st.markdown(f'<div class="quote-line">“{quote}”</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-spacer"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="glass-footer">
        <p>Information only, not legal advice · Only official sources are collected · Verify against the primary document before reliance</p>
    </div>
    """,
    unsafe_allow_html=True,
)
