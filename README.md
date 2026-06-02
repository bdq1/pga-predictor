# PGA Predictor

Weekly Monte Carlo win-probability forecast for upcoming PGA Tour tournaments.

Runs every Monday as a **claude.ai cloud routine** (runs on Anthropic's infrastructure,
no local machine needed): it finds the week's event and field, estimates each player's
strokes-gained skill from free public data, simulates the tournament tens of thousands of
times, and emails a report of win / top-5 / top-10 / top-20 / make-cut probabilities.

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
