import json
from datetime import date, timedelta
from pathlib import Path

from dateutil import parser as date_parser
import streamlit as st

st.set_page_config(page_title="Regulatory Intelligence Dashboard", page_icon="⚖", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "updates.json"

# FIXED: the line for IBBI used a semicolon ("IBBI"; "...") instead of a colon
# ("IBBI": "..."). In a Python dictionary, that's not a small style slip -
# it's invalid syntax, so the entire app would fail to even start.
STAKEHOLDER_GROUPS = {
    "MCA": "Corporate & Secretarial",
    "RBI": "Corporate & Secretarial",
    "IBBI": "Corporate & Secretarial",
    "SEBI": "Securities & Listing",
    "NSE": "Securities & Listing",
    "BSE": "Securities & Listing",
    "Ministry of Labour & Employment": "Employment Law",
}
GROUP_ORDER = ["Corporate & Secretarial", "Securities & Listing", "Employment Law"]
GROUP_BLURB = {
    "Corporate & Secretarial": "MCA, RBI, IBBI and FEMA updates for company secretaries and compliance teams.",
    "Securities & Listing": "SEBI, NSE and BSE updates for listed entities and market intermediaries.",
    "Employment Law": "Ministry of Labour & Employment updates for HR and employment-law teams.",
}

# --- Design tokens -----------------------------------------------------
# A cohesive "aged metal / official seal" family: brass, bronze, sage,
# slate - muted enough to sit quietly on a dark background together,
# rather than a rainbow of unrelated hues per authority.
AUTHORITY_SOLID = {
    "MCA": "#5B84AC", "RBI": "#6FA287", "IBBI": "#A67C52", "SEBI": "#C9A24A",
    "NSE": "#B8763F", "BSE": "#9C5B45", "Ministry of Labour & Employment": "#8577A8",
}
AUTHORITY_TINT = {a: (f"{c}26", c) for a, c in AUTHORITY_SOLID.items()}
URGENCY_STYLE = {
    "urgent": {"color": "#C1573A", "tint": "#C1573A26", "label": "Action required"},
    "pending": {"color": "#C9A24A", "tint": "#C9A24A26", "label": "Upcoming"},
    "review": {"color": "#6B7A8F", "tint": "#6B7A8F26", "label": "For review"},
}
URGENT_WINDOW_DAYS = 14


def classify_urgency(effective_date_text: str) -> str:
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
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
    :root {
        --bg: #14171C;
        --surface: #1C2027;
        --surface-raised: #262B33;
        --ink: #EDE9E1;
        --muted: #9B978F;
        --border: #333A44;
        --gold: #C9A24A;
    }
    html, body, [class*="css"], button, input, textarea {
        font-family: 'IBM Plex Sans', -apple-system, sans-serif !important;
    }
    .stApp {
        background:
            radial-gradient(900px circle at 8% -10%, rgba(201,162,74,0.07), transparent 55%),
            radial-gradient(700px circle at 100% 10%, rgba(111,162,135,0.06), transparent 55%),
            var(--bg);
    }
    .block-container { padding-top: 3rem; max-width: 1080px; color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
    [data-testid="stTabs"] p, .stMultiSelect label, .stMultiSelect span,
    .stSlider label, .stTextInput label {
        color: var(--ink);
    }
    [data-testid="stCaptionContainer"] { color: var(--muted) !important; }

    /* ---- Header: one serif title carries the weight, no eyebrow label ---- */
    .brand-title {
        font-family: 'Source Serif 4', serif;
        font-size: 3.1rem; font-weight: 600; color: var(--ink);
        margin: 0; line-height: 1.12; letter-spacing: -0.01em;
    }
    .brand-summary {
        color: var(--muted); font-size: 1rem; margin: 0.9rem 0 1.6rem 0;
        max-width: 620px; line-height: 1.6;
    }
    .brand-summary b { color: var(--ink); font-weight: 600; }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] > div {
        background: #101317;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] * { color: var(--ink) !important; }
    section[data-testid="stSidebar"] hr { border-color: var(--border) !important; }
    section[data-testid="stSidebar"] [data-baseweb="slider"] div[role="slider"] {
        background-color: var(--gold) !important; border-color: var(--gold) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="slider"] > div > div {
        background: var(--gold) !important;
    }
    section[data-testid="stSidebar"] input {
        background: var(--surface) !important; border: 1px solid var(--border) !important;
        color: var(--ink) !important;
    }
    .sidebar-brand { display:flex; align-items:center; gap:0.55rem; margin-bottom:0.3rem; }
    .sidebar-brand-mark { font-size: 1.25rem; color: var(--gold) !important; }
    .sidebar-brand-name {
        font-family: 'Source Serif 4', serif; font-weight: 600; font-size: 1.05rem;
    }
    .sidebar-brand-sub { font-size: 0.78rem; color: #6E7178 !important; margin-bottom: 1.2rem; }

    /* ---- Stats strip ---- */
    .stats-strip {
        display: flex; gap: 0; flex-wrap: wrap; background: var(--surface);
        border: 1px solid var(--border); border-radius: 10px;
        padding: 1.1rem 0.5rem; margin-bottom: 1.4rem;
    }
    .stat-block { flex: 1; min-width: 140px; text-align: center; padding: 0.3rem 0.5rem; border-right: 1px solid var(--border); }
    .stat-block:last-child { border-right: none; }
    .stat-num {
        font-family: 'Source Serif 4', serif; font-size: 2rem; font-weight: 600;
        line-height: 1; color: var(--ink);
    }
    .stat-label { color: var(--muted); font-size: 0.78rem; margin-top: 0.35rem; }

    .section-title {
        font-family: 'Source Serif 4', serif; font-size: 1.25rem; font-weight: 600;
        color: var(--ink); margin: 0.2rem 0 0.8rem 0;
    }

    .dist-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.6rem; }
    .dist-label { width: 190px; font-size: 0.86rem; color: var(--ink); flex-shrink: 0; }
    .dist-track { flex: 1; height: 8px; border-radius: 999px; background: var(--surface-raised); overflow: hidden; }
    .dist-fill { height: 100%; border-radius: 999px; }
    .dist-count { width: 26px; text-align: right; font-size: 0.84rem; color: var(--muted); }

    .urgent-preview {
        display: flex; align-items: center; gap: 0.75rem; background: var(--surface);
        border: 1px solid var(--border); border-radius: 8px; padding: 0.7rem 1rem; margin-bottom: 0.5rem;
    }
    .urgent-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .urgent-text { font-size: 0.9rem; color: var(--ink); flex: 1; }
    .urgent-when { font-size: 0.78rem; color: var(--muted); }

    /* ---- Update cards: a left accent bar encodes the authority - a
       structural device that carries real information, not decoration ---- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-left: 3px solid var(--border) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: var(--gold) !important;
        border-left-color: var(--gold) !important;
    }
    .tag-pill, .status-pill {
        display: inline-block; font-size: 0.72rem; font-weight: 600;
        padding: 0.18rem 0.65rem; border-radius: 5px; margin-right: 0.5rem;
    }
    .update-meta { color: var(--muted); font-size: 0.82rem; margin: 0.5rem 0 0.6rem 0; }
    .update-meta .sep { margin: 0 0.5rem; color: var(--border); }
    .update-title {
        font-family: 'Source Serif 4', serif; font-size: 1.15rem; font-weight: 600;
        color: var(--ink); margin: 0 0 0.7rem 0; line-height: 1.4;
    }
    .field-label {
        color: var(--muted); font-size: 0.74rem; margin-bottom: 0.15rem;
        text-transform: uppercase; letter-spacing: 0.04em;
    }
    .field-value { color: var(--ink); font-size: 0.93rem; margin-bottom: 0.6rem; line-height: 1.5; }
    .quote-line {
        border-left: 2px solid var(--gold); padding-left: 0.65rem; margin: 0.25rem 0 0.55rem 0;
        font-style: italic; color: var(--muted); font-size: 0.88rem;
    }

    .stTabs [aria-selected="true"] { color: var(--gold) !important; border-bottom-color: var(--gold) !important; }
    .stButton>button, .stLinkButton>a {
        background: var(--surface) !important; border: 1px solid var(--border) !important; color: var(--ink) !important;
    }
    .stButton>button:hover, .stLinkButton>a:hover { border-color: var(--gold) !important; color: var(--gold) !important; }

    .footer-note { color: var(--muted); font-size: 0.8rem; text-align: center; line-height: 1.8; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="brand-title">Regulatory Intelligence</p>
    <p class="brand-summary">
        <b>MCA, RBI, IBBI, SEBI, NSE, BSE and the Ministry of Labour</b>, checked daily.
        Every fact shown here is backed by a verbatim quote from the original document -
        nothing is guessed, and nothing here is legal advice.
    </p>
    """,
    unsafe_allow_html=True,
)

try:
    all_updates = json.loads(DATA_FILE.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    all_updates = []

all_updates = [u for u in all_updates if u.get("analysis_status") == "published"]

with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand"><span class="sidebar-brand-mark">⚖</span>'
        '<span class="sidebar-brand-name">Legal Tracker</span></div>'
        '<div class="sidebar-brand-sub">India, official sources only</div>',
        unsafe_allow_html=True,
    )
    st.markdown("**Filters**")
    window_days = st.slider("Show updates from the last N days", min_value=7, max_value=45, value=30, step=1)
    search_term = st.text_input("Search title or summary", "")
    st.divider()
    st.caption("Country: India, Region: APAC")
    st.caption("National sources only in this prototype.")

cutoff = (date.today() - timedelta(days=window_days)).isoformat()
updates = [u for u in all_updates if u.get("notification_date", "") >= cutoff]
if search_term.strip():
    term = search_term.strip().lower()
    updates = [u for u in updates if term in u.get("title", "").lower() or term in u.get("summary", "").lower()]
for u in updates:
    u["_group"] = STAKEHOLDER_GROUPS.get(u.get("regulatory_authority", ""), "Other")
    u["_urgency"] = classify_urgency(u.get("effective_date", ""))

strip_html = '<div class="stats-strip">'
strip_html += f'<div class="stat-block"><div class="stat-num">{len(updates)}</div><div class="stat-label">Total updates</div></div>'
for key in ("urgent", "pending", "review"):
    count = sum(1 for u in updates if u["_urgency"] == key)
    style = URGENCY_STYLE[key]
    strip_html += f'<div class="stat-block"><div class="stat-num" style="color:{style["color"]}">{count}</div><div class="stat-label">{style["label"]}</div></div>'
strip_html += "</div>"
st.markdown(strip_html, unsafe_allow_html=True)

tab_labels = ["Overview"] + [f"{g} ({sum(1 for u in updates if u['_group'] == g)})" for g in GROUP_ORDER]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.markdown('<p class="section-title">Where updates are coming from</p>', unsafe_allow_html=True)
    authority_counts = {}
    for u in updates:
        authority_counts[u["regulatory_authority"]] = authority_counts.get(u["regulatory_authority"], 0) + 1
    max_count = max(authority_counts.values(), default=1)
    if authority_counts:
        for authority, count in sorted(authority_counts.items(), key=lambda kv: kv[1], reverse=True):
            width_pct = int(100 * count / max_count) if max_count else 0
            color = AUTHORITY_SOLID.get(authority, "#7A7E86")
            st.markdown(
                f'<div class="dist-row"><div class="dist-label">{authority}</div>'
                f'<div class="dist-track"><div class="dist-fill" style="width:{width_pct}%;background:{color};"></div></div>'
                f'<div class="dist-count">{count}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No updates in the selected window yet.")

    st.markdown('<p class="section-title" style="margin-top:1.7rem;">Most urgent right now</p>', unsafe_allow_html=True)
    urgent_first = sorted(
        [u for u in updates if u["_urgency"] == "urgent"],
        key=lambda u: u.get("effective_date", ""),
    )[:5]
    if urgent_first:
        for u in urgent_first:
            color = AUTHORITY_SOLID.get(u["regulatory_authority"], "#7A7E86")
            st.markdown(
                f'<div class="urgent-preview"><span class="urgent-dot" style="background:{color}"></span>'
                f'<span class="urgent-text"><b>{u["regulatory_authority"]}</b> — {u["title"]}</span>'
                f'<span class="urgent-when">Effective {u["effective_date"]}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("Nothing flagged as immediately action-required in the current window.")

    st.markdown('<p class="section-title" style="margin-top:1.7rem;">Jump to a section</p>', unsafe_allow_html=True)
    st.caption("Use the tabs above to browse by stakeholder group: Corporate & Secretarial, Securities & Listing, or Employment Law.")

for tab, group in zip(tabs[1:], GROUP_ORDER):
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
            tint_bg, tint_text = AUTHORITY_TINT.get(update["regulatory_authority"], ("#5B616926", "#7A7E86"))
            urgency = URGENCY_STYLE[update["_urgency"]]
            with st.container(border=True):
                st.markdown(
                    f'<span class="tag-pill" style="background:{tint_bg};color:{tint_text}">{update["regulatory_authority"]}</span>'
                    f'<span class="status-pill" style="background:{urgency["tint"]};color:{urgency["color"]}">{urgency["label"]}</span>'
                    f'<div class="update-meta">{update["update_type"]}<span class="sep">/</span>{update["notification_date"]}</div>'
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
                            st.markdown(f'<div class="quote-line">"{quote}"</div>', unsafe_allow_html=True)

st.divider()
st.markdown(
    '<p class="footer-note">Information only, not legal advice.<br>'
    "Only official sources are collected. Verify against the primary document before reliance.</p>",
    unsafe_allow_html=True,
)
