# PGA Predictor

Weekly Monte Carlo win-probability forecast for upcoming PGA Tour tournaments.

Runs every Monday as a **GitHub Actions workflow** (`.github/workflows/weekly.yml`,
14:00 UTC): it pulls the week's event, field and **measured strokes-gained skill +
course-fit from the DataGolf API**, simulates the tournament 40,000 times, and emails a
two-part report — **The Favorites** (win / top-5 / top-10 / make-cut probabilities) and
**The Long Shots** (four contrarian lenses: ceiling, value-vs-market, course-fit, and
model-vs-reputation, plus a synthesis of names hitting multiple lenses).

The whole chain is one command — `python run_week.py` — wired as:
`fetch_datagolf.py` → `simulate.py` → `analyze.py` → `build_email.py` → `send_email.py`.
Email goes out via the **Resend HTTP API** (`RESEND_API_KEY`); secrets live in GitHub
Actions secrets locally in a gitignored `.env`. (An earlier claude.ai cloud-routine
attempt was abandoned: that sandbox's egress allowlist blocks DataGolf and Resend.)

- **`simulate.py`** — the simulation engine. Pure math, zero required dependencies (uses
  numpy if present, otherwise a built-in pure-Python fallback). This is the rigorous core.
- **`METHODOLOGY.md`** — how skill is estimated and how the simulation works (read this).
- **`WEEKLY_PROMPT.md`** — the exact prompt the Monday routine executes.
- **`runs/`** — saved weekly inputs (`field_<date>.json`) and outputs (`results_<date>.json`)
  for calibration over the season.
- **`examples/`** — a sample field to try the engine.

## Run it locally

```bash
# zero-dependency:
python3 simulate.py examples/sample_field.json --sims 25000

# or faster with numpy:
python3 -m venv .venv && .venv/bin/pip install numpy
.venv/bin/python simulate.py examples/sample_field.json --sims 40000 --out out.json
```

See `simulate.py`'s docstring for the input JSON schema.

## Output

Probabilities only — no betting / odds, by design. These are model estimates from
free-data skill inputs; golf is high-variance and even the favourite usually wins under
25% of the time.
