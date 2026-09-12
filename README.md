# India Legal Update Tracker

A free, portfolio-ready dashboard that collects *only approved official Indian sources* and displays the last seven days of legal and regulatory updates.

## What this MVP does now

- shows updates from the last seven days;
- filters by law area and regulatory authority;
- retains the exact first-party source link for every item;
- records the required fields: authority, country, region, state, applicability, description, summary, takeaway, notification date, effective date and update type;
- downloads the exact linked official document (PDF or HTML), extracts its text and hashes the source file for audit;
- keeps the source text locally for a reviewer; it does **not** write legal content from the index-page title;
- prevents unapproved drafts from appearing on the public dashboard.

## Start locally

```bash
cd legal_updates_agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python collector.py
streamlit run app.py
```

## Publish for free

1. Create a **public** GitHub repository and upload this folder's contents (not the parent folder).
2. In GitHub, open **Actions** and enable workflows. The collector then runs every day at 08:00 IST and commits refreshed `data/updates.json`.
3. Sign into Streamlit Community Cloud with GitHub, select the repository and set `app.py` as the entrypoint.
4. Create a free Gemini API key in Google AI Studio. In your GitHub repository, go to **Settings → Secrets and variables → Actions**, then create a secret named `GEMINI_API_KEY`. Do not put it in the code or repository.
5. Set the Streamlit app to public and share the `streamlit.app` link in your LinkedIn post.

## Non-hallucination rule

The process is deliberately two-stage:

1. **Evidence capture:** the collector finds an official index entry, follows its exact official link, saves the source document, extracts its text, stores a SHA-256 fingerprint and records the exact public URL.
2. **Controlled automatic analysis:** Gemini receives only the captured primary-source text and returns structured fields with verbatim evidence quotations. `gemini_analyser.py` rejects the whole draft if a required field lacks evidence, its quotation is not found in the source, its update type is outside the approved list, or its effective date is not quoted. Passing drafts are automatically published; rejected drafts remain off the public dashboard.

This is a strong guardrail, not a guarantee that any generative model will never make a poor paraphrase. The displayed evidence, exact primary link, fixed categories, zero-temperature output and fail-closed validator make each published update auditable. The site must state that it is information only and not legal advice.

## Source policy

`data/sources.json` is the source allow-list. Add a source only after confirming its URL belongs to the official authority. This starter includes public index pages for MCA, SEBI and Ministry of Labour & Employment. RBI, NSE, BSE, Gazette of India and state sources should be added one at a time after their current index/API behaviour is tested. NSE and BSE are market infrastructure institutions, not Government of India departments; label them accurately in the UI.

## Important limits

- This is an information-retrieval tool, not legal advice.
- No collector can prove completeness. Source pages, PDF content and statutory effective dates must be reviewed by a legal professional.
- The current collector only accepts items with an explicit date on the official index page; it intentionally rejects undated pages instead of guessing.
- State-specific labour updates require a separate allow-listed source per state.

## Next build steps

1. Test each configured source and tighten its parser around the site's actual table/list markup.
2. Add one review queue so a human approves every summary before it is public.
3. Add RBI, NSE, BSE and e-Gazette adapters, each with a documented primary-source URL.
4. Add state labour departments, beginning with the states you need.
5. Optionally use an AI model only to draft a summary; preserve the primary link and require human approval.
