# Methodology

The goal is a **mathematically honest** weekly forecast of PGA Tour outcomes: win,
top-5, top-10, top-20 and make-cut probabilities for every player in the field,
produced by a Monte Carlo simulation rather than gut feel.

## 1. Player skill (the model's input)

Each player gets a **skill** value expressed in *strokes-gained per round versus the
field* (higher = better). Rough scale:

| Skill (SG/round) | Tier |
|---|---|
| +2.2 … +2.8 | world #1–3, peak form |
| +1.6 … +2.1 | elite (top ~10) |
| +1.1 … +1.5 | strong (top ~30) |
| +0.6 … +1.0 | solid tour regular |
| +0.1 … +0.5 | fringe |
| −0.5 … 0.0 | below tour average |

Estimated each week from **free public data**, in priority order:

1. **DataGolf free skill ratings / rankings** — they publish a total skill estimate in
   strokes-gained terms; map it directly to `skill`. Best available free signal.
2. **Official World Golf Ranking + recent strokes-gained / form** — when a player isn't
   covered above, infer skill from OWGR position and last ~5 results.

Free data is noisier than a paid feed (e.g. DataGolf's API), so treat skill values as
estimates. The simulation **math** is rigorous; the **inputs** are best-effort. Swapping
in a paid data feed later changes only the input layer — the engine is unchanged.

### Course-fit adjustment

An optional per-player `adjustment` (default 0, capped at roughly ±0.6) nudges skill for
**course history** and **course-type fit** (e.g. bombers at a long course, elite putters
on tricky greens) and notable **weather** edges. Kept small on purpose — course fit is a
real but modest effect and over-fitting it is the fastest way to ruin a forecast.

## 2. The simulation

For each of N simulated tournaments (default 25,000), every player's single-round
performance is:

```
P = effective_skill + form + round_noise
    effective_skill = skill + adjustment
    form        ~ Normal(0, σ_form)    drawn ONCE per player per week
    round_noise ~ Normal(0, σ_round)   independent each round
```

- **`form`** correlates a player's four rounds — it models someone being "on" or "off"
  all week. This is essential: a model with independent rounds badly *underrates*
  favourites, because winning would require four independent great rounds.
- Single-round SD around a player's mean is `sqrt(σ_form² + σ_round²) ≈ 2.8` strokes,
  matching observed round-to-round strokes-gained variability of tour pros.
- Defaults: `σ_form = 1.0`, `σ_round = 2.6` (tunable in the field JSON).

After 36 holes a **cut** is applied (default top 65 + ties); missed-cut players cannot
place. Players are then ranked by 72-hole total strokes-gained. Tallying outcomes across
all simulations yields the probabilities.

## 3. What it deliberately does NOT do

- **No betting / odds.** Probabilities only, by design.
- No claim of precision beyond the data. These are model estimates, not certainties —
  golf is high-variance and even the favourite usually wins well under 25% of the time.

## Calibration over time

Each week's `field.json` (inputs) and `results.json` (outputs) are saved in `runs/`. Over
a season these allow checking calibration (do ~10%-to-win players win ~10% of the time?)
and tuning `σ_form` / `σ_round` and the skill-estimation mapping.
