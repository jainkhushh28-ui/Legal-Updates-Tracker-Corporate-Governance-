import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="India Legal Update Tracker", page_icon="⚖️", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "updates.json"

st.title("India Legal Update Tracker")
st.caption("Official-source monitoring dashboard · Latest seven days · Information only, not legal advice")

try:
    updates = json.loads(DATA_FILE.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    updates = []

cutoff = (date.today() - timedelta(days=7)).isoformat()
updates = [u for u in updates if u.get("notification_date", "") >= cutoff and u.get("analysis_status") == "published"]

areas = sorted({u["law_area"] for u in updates}) or ["Corporate and secretarial", "Labour and employment", "Securities and capital markets"]
authorities = sorted({u["regulatory_authority"] for u in updates})

with st.sidebar:
    st.header("Filter updates")
    selected_areas = st.multiselect("Law area", areas, default=areas)
    selected_authorities = st.multiselect("Authority", authorities, default=authorities)
    st.caption("Country: India · Region: APAC · Coverage: national sources in this MVP")

filtered = [u for u in updates if u["law_area"] in selected_areas and u["regulatory_authority"] in selected_authorities]
st.metric("Updates published in the past 7 days", len(filtered))

if not filtered:
    st.info("No verified updates are available yet. Run the collector, then refresh this dashboard.")
else:
    for update in filtered:
        with st.container(border=True):
            st.subheader(update["title"])
            st.caption(f'{update["regulatory_authority"]} · {update["notification_date"]} · {update["update_type"]}')
            left, right = st.columns(2)
            with left:
                st.markdown(f'**Applicability:** {update["applicability"]}')
                st.markdown(f'**Effective date:** {update["effective_date"]}')
            with right:
                st.markdown(f'**Summary:** {update["summary"]}')
                st.markdown(f'**Takeaway:** {update["takeaway"]}')
            st.link_button("Open exact primary source", update["primary_source_link"])
            with st.expander("Source evidence used for this update"):
                for field, quotes in update.get("field_evidence", {}).items():
                    st.markdown(f"**{field.replace('_', ' ').title()}**")
                    for quote in quotes:
                        st.caption(f'“{quote}”')

st.divider()
st.caption("Only configured official sources are collected. Dates and legal effects must be verified against the primary document before reliance.")
