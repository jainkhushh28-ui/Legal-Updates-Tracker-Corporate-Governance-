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
# Black / navy / orange / cream family — cohesive rather than a rainbow of
# unrelated hues per authority.
AUTHORITY_SOLID = {
    "MCA": "#1D3557", "RBI": "#3A5A7A", "SEBI": "#7A5326",
    "NSE": "#6B4423", "BSE": "#E07A29", "Ministry of Labour & Employment": "#A6431E",
}
AUTHORITY_TINT = {a: (f"{c}22", c) for a, c in AUTHORITY_SOLID.items()}
URGENCY_STYLE = {
    "urgent": {"color": "#C1502E", "tint": "#C1502E22", "label": "Action required"},
    "pending": {"color": "#A6791E", "tint": "#A6791E22", "label": "Upcoming"},
    "review": {"color": "#33507A", "tint": "#33507A22", "label": "For review"},
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
    <style>
    :root {
        --cream: #F6F1E7;
        --ink: #16181C;
        --navy: #1D3557;
        --orange: #E07A29;
        --muted: #6B6560;
        --card: #FFFDF8;
        --border: #E4DCC9;
    }
    html, body, [class*="css"], button, input, textarea {
        font-family: Georgia, 'Times New Roman', serif !important;
    }
    .stApp {
        background:
            radial-gradient(650px circle at 4% -6%, rgba(29,53,87,0.10), transparent 60%),
            radial-gradient(650px circle at 100% 100%, rgba(224,122,41,0.12), transparent 60%),
            var(--cream);
    }
    .block-container { padding-top: 0.4rem; max-width: 1080px; }

    .brand-kicker { font-size: 0.8rem; letter-spacing: 0.08em; color: var(--orange); font-weight: bold; margin-bottom: 0.3rem; }
    .brand-title { font-size: 4rem; font-weight: 700; color: var(--navy); margin: 0; line-height: 1.02; }
    .brand-summary { color: var(--muted); font-size: 0.92rem; margin: 0.55rem 0 1.3rem 0; max-width: 620px; }

    /* ---- Sidebar: black / cream / orange ---- */
    section[data-testid="stSidebar"] > div {
        background: var(--ink);
        border-right: 3px solid var(--orange);
    }
    section[data-testid="stSidebar"] * { color: var(--cream) !important; font-family: Georgia, serif !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(246,241,231,0.2) !important; }
    section[data-testid="stSidebar"] [data-baseweb="slider"] div[role="slider"] {
        background-color: var(--orange) !important; border-color: var(--orange) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="slider"] > div > div {
        background: var(--orange) !important;
    }
    section[data-testid="stSidebar"] input {
        background: #23262E !important; border: 1px solid rgba(224,122,41,0.4) !important;
    }
    .sidebar-brand { display:flex; align-items:center; gap:0.5rem; margin-bottom:0.3rem; }
    .sidebar-brand-mark { font-size: 1.3rem; color: var(--orange) !important; }
    .sidebar-brand-name { font-weight: 700; font-size: 1rem; }
    .sidebar-brand-sub { font-size: 0.76rem; color: #B7ADA0 !important; margin-bottom: 1.1rem; }

    /* ---- Stats strip ---- */
    .stats-strip { display: flex; gap: 0; flex-wrap: wrap; background: var(--ink); border-radius: 14px; padding: 1rem 0.4rem; margin-bottom: 1.3rem; }
    .stat-block { flex: 1; min-width: 140px; text-align: center; padding: 0.3rem 0.5rem; border-right: 1px solid rgba(246,241,231,0.14); }
    .stat-block:last-child { border-right: none; }
    .stat-num { font-size: 1.9rem; font-weight: 700; line-height: 1; color: var(--cream); }
    .stat-label { color: #B7ADA0; font-size: 0.78rem; margin-top: 0.3rem; }

    .section-title { font-size: 1.2rem; font-weight: 700; color: var(--navy); margin: 0.2rem 0 0.7rem 0; }

    .dist-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.55rem; }
    .dist-label { width: 190px; font-size: 0.86rem; color: var(--ink); flex-shrink: 0; }
    .dist-track { flex: 1; height: 9px; border-radius: 999px; background: var(--border); overflow: hidden; }
    .dist-fill { height: 100%; border-radius: 999px; }
    .dist-count { width: 26px; text-align: right; font-size: 0.84rem; color: var(--muted); }

    .urgent-preview { display: flex; align-items: center; gap: 0.7rem; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 0.65rem 0.9rem; margin-bottom: 0.5rem; }
    .urgent-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .urgent-text { font-size: 0.88rem; color: var(--ink); flex: 1; }
    .urgent-when { font-size: 0.78rem; color: var(--muted); }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 2px rgba(22,24,28,0.04), 0 6px 16px rgba(22,24,28,0.05);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: var(--orange) !important;
    }
    .tag-pill, .status-pill { display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 0.16rem 0.6rem; border-radius: 999px; margin-right: 0.4rem; }
    .update-meta { color: var(--muted); font-size: 0.82rem; margin: 0.4rem 0 0.5rem 0; }
    .update-title { font-size: 1.1rem; font-weight: 700; color: var(--ink); margin: 0 0 0.6rem 0; line-height: 1.4; }
    .field-label { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.1rem; }
    .field-value { color: var(--ink); font-size: 0.92rem; margin-bottom: 0.55rem; }
    .quote-line { border-left: 2px solid var(--orange); padding-left: 0.6rem; margin: 0.2rem 0 0.5rem 0; font-style: italic; color: var(--muted); font-size: 0.88rem; }

    .stTabs [aria-selected="true"] { color: var(--orange) !important; border-bottom-color: var(--orange) !important; }
    .stButton>button:hover, .stLinkButton>a:hover { border-color: var(--orange) !important; color: var(--orange) !important; }

    .footer-note { color: var(--muted); font-size: 0.8rem; text-align: center; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="brand-kicker">INDIA · OFFICIAL SOURCES ONLY</div>
    <p class="brand-title">Regulatory Intelligence</p>
    <p class="brand-summary">Verified legal updates from MCA, RBI, SEBI, NSE, BSE &amp; Labour — every fact backed by a verbatim source quote.</p>
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
        '<div class="sidebar-brand-sub">India · Official sources only</div>',
        unsafe_allow_html=True,
    )
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
            color = AUTHORITY_SOLID.get(authority, "#8A8D95")
            st.markdown(
                f'<div class="dist-row"><div class="dist-label">{authority}</div>'
                f'<div class="dist-track"><div class="dist-fill" style="width:{width_pct}%;background:{color};"></div></div>'
                f'<div class="dist-count">{count}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No updates in the selected window yet.")

    st.markdown('<p class="section-title" style="margin-top:1.6rem;">Most urgent right now</p>', unsafe_allow_html=True)
    urgent_first = sorted(
        [u for u in updates if u["_urgency"] == "urgent"],
        key=lambda u: u.get("effective_date", ""),
    )[:5]
    if urgent_first:
        for u in urgent_first:
            color = AUTHORITY_SOLID.get(u["regulatory_authority"], "#8A8D95")
            st.markdown(
                f'<div class="urgent-preview"><span class="urgent-dot" style="background:{color}"></span>'
                f'<span class="urgent-text"><b>{u["regulatory_authority"]}</b> — {u["title"]}</span>'
                f'<span class="urgent-when">Effective {u["effective_date"]}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("Nothing flagged as immediately action-required in the current window.")

    st.markdown('<p class="section-title" style="margin-top:1.6rem;">Jump to a section</p>', unsafe_allow_html=True)
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
            tint_bg, tint_text = AUTHORITY_TINT.get(update["regulatory_authority"], ("#5B616922", "#5B6169"))
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

st.divider()
st.markdown(
    '<p class="footer-note">Information only, not legal advice · Only official sources are collected · '
    "Verify against the primary document before reliance.</p>",
    unsafe_allow_html=True,
)
