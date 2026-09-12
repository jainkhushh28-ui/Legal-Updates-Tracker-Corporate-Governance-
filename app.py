import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="India Legal Update Tracker", page_icon="⚖️", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "updates.json"

# Maps each authority to the stakeholder group your audience actually cares
# about. This is a display grouping only — it does not change the underlying
# law_area field used elsewhere, just how the dashboard is organised for
# corporate secretarial, securities/listing and employment law readers.
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
AUTHORITY_COLOR = {
    "MCA": "#2563eb",
    "RBI": "#7c3aed",
    "SEBI": "#0891b2",
    "NSE": "#059669",
    "BSE": "#d97706",
    "Ministry of Labour & Employment": "#dc2626",
}

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    .update-card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 1rem;
    }
    .authority-badge {
        display: inline-block;
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        margin-right: 0.5rem;
    }
    .update-meta { color: rgba(128,128,128,0.9); font-size: 0.85rem; margin-bottom: 0.6rem; }
    .quote-block {
        border-left: 3px solid rgba(128,128,128,0.35);
        padding-left: 0.75rem;
        margin: 0.3rem 0 0.7rem 0;
        font-style: italic;
        color: rgba(160,160,160,1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ India Legal Update Tracker")
st.caption("Official-source monitoring dashboard · Information only, not legal advice")

try:
    all_updates = json.loads(DATA_FILE.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    all_updates = []

all_updates = [u for u in all_updates if u.get("analysis_status") == "published"]

with st.sidebar:
    st.header("Filters")
    window_days = st.slider("Show updates from the last N days", min_value=7, max_value=45, value=30, step=1)
    st.caption("Different sources are collected on different lookback windows; widen this if a category looks empty.")
    search_term = st.text_input("Search title or summary", "")
    st.divider()
    st.caption("Country: India · Region: APAC · Coverage: national sources in this prototype")

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

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total updates", len(updates))
for col, group in zip((col2, col3, col4), GROUP_ORDER):
    col.metric(group, sum(1 for u in updates if u["_group"] == group))

st.divider()

tabs = st.tabs([f"{g}  ({sum(1 for u in updates if u['_group'] == g)})" for g in GROUP_ORDER])

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
                f"No verified {group.lower()} updates in the selected window yet. "
                "Try widening the day range in the sidebar, or check back after the next collection run."
            )
            continue

        authorities = sorted({u["regulatory_authority"] for u in group_updates})
        selected_authorities = st.multiselect(
            "Filter by authority", authorities, default=authorities, key=f"auth_{group}"
        )
        for update in group_updates:
            if update["regulatory_authority"] not in selected_authorities:
                continue
            color = AUTHORITY_COLOR.get(update["regulatory_authority"], "#6b7280")
            with st.container():
                st.markdown(
                    f'<div class="update-card">'
                    f'<span class="authority-badge" style="background:{color}">{update["regulatory_authority"]}</span>'
                    f'<strong>{update["title"]}</strong>'
                    f'<div class="update-meta">{update["notification_date"]} · {update["update_type"]} · {update["law_area"]}</div>',
                    unsafe_allow_html=True,
                )
                left, right = st.columns(2)
                with left:
                    st.markdown(f'**Applicability:** {update["applicability"]}')
                    st.markdown(f'**Effective date:** {update["effective_date"]}')
                with right:
                    st.markdown(f'**Summary:** {update["summary"]}')
                    st.markdown(f'**Takeaway:** {update["takeaway"]}')
                st.link_button("Open exact primary source ↗", update["primary_source_link"])
                with st.expander("Source evidence used for this update"):
                    for field, quotes in update.get("field_evidence", {}).items():
                        st.markdown(f"**{field.replace('_', ' ').title()}**")
                        for quote in quotes:
                            st.markdown(f'<div class="quote-block">“{quote}”</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.caption(
    "Only configured official sources are collected. Dates and legal effects must be verified "
    "against the primary document before reliance. This tool provides information only, not legal advice."
)
