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
AUTHORITY_TINT = {
    "MCA": ("rgba(66,99,148,0.16)", "#33518A"),
    "RBI": ("rgba(122,92,163,0.16)", "#684D96"),
    "SEBI": ("rgba(58,128,116,0.16)", "#2C7566"),
    "NSE": ("rgba(66,140,92,0.16)", "#357C4E"),
    "BSE": ("rgba(197,143,45,0.18)", "#8F6A1E"),
    "Ministry of Labour & Employment": ("rgba(178,84,72,0.16)", "#963F35"),
}
AUTHORITY_SOLID = {
    "MCA": "#4263A0", "RBI": "#7A5CA3", "SEBI": "#3A8074",
    "NSE": "#428C5C", "BSE": "#C58F2D", "Ministry of Labour & Employment": "#B25448",
}
URGENCY_STYLE = {
    "urgent": {"color": "#9E5449", "tint": "rgba(158,84,73,0.16)", "label": "Action required"},
    "pending": {"color": "#96792A", "tint": "rgba(150,121,42,0.16)", "label": "Upcoming"},
    "review": {"color": "#3F7A68", "tint": "rgba(63,122,104,0.16)", "label": "For review"},
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
        --glass-bg: rgba(255,255,255,0.58);
        --glass-bg-strong: rgba(255,255,255,0.72);
        --glass-border: rgba(255,255,255,0.55);
        --ink: #2A2C33;
        --muted: #6B6E76;
    }
    html, body, [class*="css"], button, input, textarea,
    .stMarkdown, .stTextInput, .stSlider, .stTabs, .stMultiSelect {
        font-family: Georgia, 'Times New Roman', serif !important;
    }

    .stApp {
        background:
            radial-gradient(620px circle at 6% -4%, rgba(122,92,163,0.22), transparent 60%),
            radial-gradient(620px circle at 96% 108%, rgba(66,140,92,0.20), transparent 60%),
            radial-gradient(520px circle at 82% 8%, rgba(178,84,72,0.16), transparent 55%),
            linear-gradient(160deg, #ECF0F6 0%, #F2ECF6 45%, #EBF3EE 100%);
        background-attachment: fixed;
    }
    .block-container { padding-top: 0; max-width: 1080px; }

    .glass-header {
        position: sticky; top: 0; z-index: 999;
        margin: 0 -1rem 1.2rem -1rem;
        padding: 1.6rem 1.8rem 1.3rem 1.8rem;
        background: var(--glass-bg);
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        border: 1px solid var(--glass-border); border-top: none;
        box-shadow: 0 1px 2px rgba(31,41,55,0.04), 0 8px 24px rgba(31,41,55,0.08), 0 20px 40px rgba(31,41,55,0.05);
    }
    .brand-kicker { font-size: 0.78rem; letter-spacing: 0.05em; color: #7A5CA3; font-weight: bold; margin-bottom: 0.2rem; }
    .brand-title { font-size: 2.7rem; font-weight: 700; color: var(--ink); margin: 0; line-height: 1.1; }
    .brand-summary { color: var(--muted); font-size: 1rem; margin-top: 0.5rem; }

    section[data-testid="stSidebar"] > div {
        background: rgba(255,255,255,0.5);
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        border-right: 1px solid rgba(255,255,255,0.5);
    }

    /* Dark glass "command strip" for the headline numbers */
    .stats-strip {
        display: flex; gap: 0; flex-wrap: wrap;
        background: rgba(24,26,32,0.72);
        backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 1.1rem 0.5rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2), 0 16px 32px rgba(0,0,0,0.22);
    }
    .stat-block { flex: 1; min-width: 150px; text-align: center; padding: 0.4rem 0.6rem; border-right: 1px solid rgba(255,255,255,0.1); }
    .stat-block:last-child { border-right: none; }
    .stat-num { font-size: 2rem; font-weight: 700; line-height: 1; color: #FFFFFF; }
    .stat-label { color: #B7B9C2; font-size: 0.8rem; margin-top: 0.3rem; }

    .section-title { font-size: 1.25rem; font-weight: 700; color: var(--ink); margin: 0.2rem 0 0.7rem 0; }

    .dist-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.55rem; }
    .dist-label { width: 190px; font-size: 0.88rem; color: var(--ink); flex-shrink: 0; }
    .dist-track { flex: 1; height: 10px; border-radius: 999px; background: rgba(107,110,118,0.14); overflow: hidden; }
    .dist-fill { height: 100%; border-radius: 999px; }
    .dist-count { width: 28px; text-align: right; font-size: 0.85rem; color: var(--muted); }

    .urgent-preview {
        display: flex; align-items: center; gap: 0.7rem;
        background: var(--glass-bg-strong); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
        border: 1px solid var(--glass-border); border-radius: 12px;
        padding: 0.7rem 0.95rem; margin-bottom: 0.55rem;
    }
    .urgent-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .urgent-text { font-size: 0.9rem; color: var(--ink); flex: 1; }
    .urgent-when { font-size: 0.8rem; color: var(--muted); }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--glass-bg-strong) !important;
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        box-shadow: 0 1px 2px rgba(31,41,55,0.03), 0 12px 28px rgba(31,41,55,0.07), 0 24px 48px rgba(31,41,55,0.04);
    }
    .tag-pill, .status-pill {
        display: inline-block; font-size: 0.72rem; font-weight: 700;
        padding: 0.16rem 0.6rem; border-radius: 999px; margin-right: 0.4rem;
    }
    .update-meta { color: var(--muted); font-size: 0.82rem; margin: 0.4rem 0 0.5rem 0; }
    .update-title { font-size: 1.12rem; font-weight: 700; color: var(--ink); margin: 0 0 0.6rem 0; line-height: 1.4; }
    .field-label { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.1rem; }
    .field-value { color: var(--ink); font-size: 0.92rem; margin-bottom: 0.55rem; }
    .quote-line {
        border-left: 2px solid rgba(107,110,118,0.3); padding-left: 0.6rem; margin: 0.2rem 0 0.5rem 0;
        font-style: italic; color: var(--muted); font-size: 0.88rem;
    }

    .glass-footer {
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
        padding: 0.7rem 1.6rem;
        background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
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
        <p class="brand-summary">Verified legal updates from MCA, RBI, SEBI, NSE, BSE &amp; Labour — every fact backed by a verbatim source quote.</p>
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
    updates = [u for u in updates if term in u.get("title", "").lower() or term in u.get("summary", "").lower()]
for u in updates:
    u["_group"] = STAKEHOLDER_GROUPS.get(u.get("regulatory_authority", ""), "Other")
    u["_urgency"] = classify_urgency(u.get("effective_date", ""))

# ---- Dark command strip ----
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

# ---- Overview tab: distribution + urgent preview, doubling as a quick-nav landing section ----
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
    urgent_first = sorted(updates, key=lambda u: (u["_urgency"] != "urgent", u.get("notification_date", "")), reverse=False)
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
        st.caption("Nothing flagged as immediately action-required in the current window — good sign, or worth widening the day range to check.")

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
            tint_bg, tint_text = AUTHORITY_TINT.get(update["regulatory_authority"], ("rgba(107,110,118,0.16)", "#5B6169"))
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
