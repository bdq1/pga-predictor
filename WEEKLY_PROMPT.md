# Weekly routine prompt

This is the procedure the scheduled claude.ai routine runs every Monday. The
routine itself injects the secrets (DataGolf key + Gmail SMTP credentials) as a
`.env` file at runtime — they are NOT stored in this public repo.

The repository is already checked out and the engine is built. Your job is to run
the pipeline for this week's PGA Tour event and email the report. Do NOT
hand-estimate skill — real data comes from the DataGolf API.

---

You are generating this week's PGA Tour win-probability forecast (two parts:
"The Favorites" and "The Long Shots"). Work in the repository root.

## Steps

1. **Environment.** Ensure Python deps are available: `python3 -m venv .venv && .venv/bin/pip install -q numpy` (numpy is optional — `simulate.py` has a pure-Python fallback — but it makes 40k sims fast). Confirm `.env` exists with `DATAGOLF_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `REPORT_TO` (and optionally `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` for the local SMTP fallback). Load it: `set -a; . ./.env; set +a`. Email goes out via the **Resend HTTP API** — outbound SMTP is blocked in the cloud sandbox, so `RESEND_API_KEY` is what makes the send work here.

2. **Determine this week's event + cut rule.** Find today's date and the PGA Tour
   event teeing off this Thursday (`DATE=YYYY-MM-DD` for that Thursday). Web-search
   the event to determine the **36-hole cut rule**, which sets `--cut-line`:
   - Standard event → `65`
   - Signature event WITH a cut (e.g. the Memorial) → `50`
   - No-cut signature event (limited ~70-player field) → `0`
   - Major → use that major's rule (often `50`, sometimes `60`)
   If there's an opposite-field event, model only the main event but mention the other.
   The DataGolf feeds auto-target the current upcoming PGA event, so `--date` only
   labels the output files.

3. **Fetch real inputs** from DataGolf:
   `.venv/bin/python fetch_datagolf.py --date $DATE --cut-line <N>`
   Writes `runs/field_$DATE.json` (skill + course-fit) and `runs/dg_$DATE.json`
   (DataGolf probs, std-dev, de-vigged sportsbook odds, OWGR vs DG rank).

4. **Simulate:**
   `.venv/bin/python simulate.py runs/field_$DATE.json --sims 40000 --seed 7 --out runs/results_$DATE.json`

5. **Analyze (two-part forecast):**
   `.venv/bin/python analyze.py --date $DATE`
   Builds Part 1 (favorites) + Part 2 (4 contrarian lenses + synthesis) →
   `runs/analysis_$DATE.json`.

6. **Build the email:**
   `.venv/bin/python build_email.py --date $DATE`  (prints the subject line) →
   `runs/email_$DATE.{html,txt}`.

7. **Send it:**
   `.venv/bin/python send_email.py --subject "$(.venv/bin/python build_email.py --date $DATE)" --html runs/email_$DATE.html --text runs/email_$DATE.txt`
   This emails the report to `REPORT_TO` via Gmail SMTP.

8. **Save the calibration history.** Commit the new `runs/*_$DATE.*` files
   (`git add runs && git commit -m "forecast: <Event> $DATE" && git push`).
   This builds the season-long record so calibration can be checked later
   (do ~10%-to-win players win ~10% of the time?).

## Quality bar

The math in `simulate.py` is rigorous; the inputs are now real measured DataGolf
strokes-gained data, so do NOT invent or override skill numbers. If a DataGolf feed
fails or the field is incomplete, say so explicitly in a short note rather than
fabricating. Sanity-check before sending: the favourite should be well under 25% to
win, and the field-wide make-cut percentages should be plausible.
