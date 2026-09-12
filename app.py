import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="India Legal Update Tracker", page_icon="⚖", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "updates.json"

# Maps each authority to the stakeholder group your audience actually cares
# about. Display grouping only — it does not change the underlying law_area
# field used elsewhere.
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
# A restrained, harmonious palette — not the stock blue/purple/teal defaults.
AUTHORITY_COLOR = {
    "MCA": "#35507A",
    "RBI": "#6B4A7A",
    "SEBI": "#2F6F6F",
    "NSE": "#3F7D53",
    "BSE": "#A9762F",
    "Ministry of Labour & Employment": "#8C3B3B",
}

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

    :root {
        --ink: #1C2333;
        --muted: #5B6169;
        --rule: #D3D6CC;
        --paper: #F4F5F1;
    }
    html, body, [class*="css"]  { font-family: 'IBM Plex Sans', sans-serif; }
    .block-container { padding-top: 1.6rem; max-width: 980px; }

    .masthead { border-bottom: 2px solid var(--ink); padding-bottom: 0.9rem; margin-bottom: 0.2rem; }
    .masthead-title {
        font-family: 'Source Serif 4', serif;
        font-weight: 700;
        font-size: 2.1rem;
        color: var(--ink);
        margin: 0;
        line-height: 1.15;
    }
    .masthead-sub { color: var(--muted); font-size: 0.95rem; margin-top: 0.35rem; }

    .stat-strip { display: flex; gap: 2.4rem; padding: 1rem 0; border-bottom: 1px solid var(--rule); margin-bottom: 0.4rem; flex-wrap: wrap; }
    .stat-num { font-family: 'Source Serif 4', serif; font-size: 1.5rem; color: var(--ink); line-height: 1; }
    .stat-label { color: var(--muted); font-size: 0.82rem; margin-top: 0.15rem; }

    .group-note { color: var(--muted); font-size: 0.92rem; margin-bottom: 0.6rem; }

    .register-item { border-bottom: 1px solid var(--rule); padding: 0.95rem 0 0.95rem 0.95rem; margin-bottom: 0.1rem; }
    .register-head { display: flex; align-items: baseline; gap: 0.55rem; flex-wrap: wrap; }
    .register-authority { font-weight: 600; font-size: 0.78rem; letter-spacing: 0.01em; }
    .register-tick { display: inline-block; width: 1px; height: 0.8rem; background: var(--rule); }
    .register-meta { color: var(--muted); font-size: 0.82rem; }
    .register-title {
        font-family: 'Source Serif 4', serif;
        font-size: 1.08rem;
        font-weight: 600;
        color: var(--ink);
        margin: 0.3rem 0 0.55rem 0;
        line-height: 1.35;
    }
    .field-label { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.1rem; }
    .field-value { color: var(--ink); font-size: 0.92rem; margin-bottom: 0.6rem; }
    .quote-line {
        border-left: 2px solid var(--rule);
        padding-left: 0.65rem;
        margin: 0.25rem 0 0.6rem 0;
        font-style: italic;
        color: var(--muted);
        font-size: 0.88rem;
    }
    .footer-note { color: var(--muted); font-size: 0.82rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="masthead">
        <p class="masthead-title">India Legal Update Tracker</p>
        <p class="masthead-sub">A register of verified updates from official sources — information only, not legal advice.</p>
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
    st.caption("Sources are collected on different windows; widen this if a group looks empty.")
    search_term = st.text_input("Search title or summary", "")
    st.divider()
    st.caption("Country: India · Region: APAC · National sources only in this prototype.")

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

stat_html = f'<div class="stat-strip">'
stat_html += f'<div><div class="stat-num">{len(updates)}</div><div class="stat-label">Total updates</div></div>'
for group in GROUP_ORDER:
    count = sum(1 for u in updates if u["_group"] == group)
    stat_html += f'<div><div class="stat-num">{count}</div><div class="stat-label">{group}</div></div>'
stat_html += "</div>"
st.markdown(stat_html, unsafe_allow_html=True)

tabs = st.tabs(GROUP_ORDER)

for tab, group in zip(tabs, GROUP_ORDER):
    with tab:
        st.markdown(f'<p class="group-note">{GROUP_BLURB[group]}</p>', unsafe_allow_html=True)
        group_updates = sorted(
            (u for u in updates if u["_group"] == group),
            key=lambda u: u.get("notification_date", ""),
            reverse=True,
        )
        if not group_updates:
            st.info(
                f"No verified updates in this group within the selected window. "
                f"Widen the day range in the sidebar, or check back after the next collection run."
            )
            continue

        authorities = sorted({u["regulatory_authority"] for u in group_updates})
        selected_authorities = st.multiselect(
            "Authority", authorities, default=authorities, key=f"auth_{group}", label_visibility="collapsed"
        )
        for update in group_updates:
            if update["regulatory_authority"] not in selected_authorities:
                continue
            color = AUTHORITY_COLOR.get(update["regulatory_authority"], "#5B6169")
            st.markdown(
                f'<div class="register-item" style="border-left: 3px solid {color};">'
                f'<div class="register-head">'
                f'<span class="register-authority" style="color:{color}">{update["regulatory_authority"]}</span>'
                f'<span class="register-tick"></span>'
                f'<span class="register-meta">{update["update_type"]}</span>'
                f'<span class="register-tick"></span>'
                f'<span class="register-meta">{update["notification_date"]}</span>'
                f'</div>'
                f'<p class="register-title">{update["title"]}</p>',
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
            st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown(
    '<p class="footer-note">Only configured official sources are collected, and only items matching the '
    "project's editorial capture policy (general applicability, operative language, tracked compliance topics) "
    "are published. Dates and legal effects must still be verified against the primary document before reliance. "
    "This tool provides information only, not legal advice.</p>",
    unsafe_allow_html=True,
)
