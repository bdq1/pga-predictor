#!/usr/bin/env python3
"""
PGA tournament Monte Carlo simulator.

Math model (per simulated tournament):

  Each player i has a baseline skill in *strokes-gained per round vs the field*
  (higher = better). The data layer estimates this each week from public signals
  (DataGolf free skill ratings, OWGR, recent strokes-gained / form), and may add a
  per-player `adjustment` for course fit, course history, and forecast weather.

  effective_skill_i = skill_i + adjustment_i        # expected SG / round

  A player's performance in a single round is:

      P_ir = effective_skill_i  +  f_i  +  e_ir

    f_i  ~ Normal(0, SIGMA_FORM)   drawn ONCE per player per simulated tournament.
                                   Captures a player being "on" or "off" all week
                                   (rounds within a week are correlated). This is
                                   what makes favourites' win odds realistic — a
                                   model with independent rounds badly underrates them.
    e_ir ~ Normal(0, SIGMA_ROUND)  independent round-to-round noise.

  Single-round SD around a player's mean is sqrt(SIGMA_FORM^2 + SIGMA_ROUND^2),
  tuned to ~2.8 strokes, which matches observed round-to-round SG variability of
  PGA Tour pros.

  Cut: after 36 holes, the top CUT_LINE players (and ties) advance. Missed-cut
  players cannot finish in the money and are excluded from top-N / win counts.

  Tournament result = rank players by 4-round total SG (higher = better).

  Running tens of thousands of independent simulated tournaments and tallying
  outcomes yields win / top-5 / top-10 / top-20 / make-cut probabilities and an
  expected finishing position.

Output is intentionally *probabilities only* (no betting/odds).

Usage:
    python simulate.py field.json [--sims 25000] [--seed 0] [--out results.json]

Input JSON schema (field.json):
{
  "event": "The Memorial Tournament",
  "course": "Muirfield Village GC",
  "date": "2026-06-01",
  "sims": 25000,                 # optional, CLI overrides
  "cut_line": 65,               # optional, players making the cut (+ ties); 0/absent = no cut
  "params": {                    # optional overrides of the model constants
      "sigma_form": 1.0,
      "sigma_round": 2.6
  },
  "players": [
     {"name": "Scottie Scheffler", "skill": 2.6, "adjustment": 0.3, "notes": "elite ball-striking, course fit A"},
     {"name": "Rory McIlroy",      "skill": 2.1, "adjustment": 0.1},
     ...
  ]
}

`skill` is required per player (SG/round vs field). `adjustment` defaults to 0.
"""

import argparse
import json
import sys

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - cloud sandbox may lack numpy
    HAVE_NUMPY = False

# --- Model constants (see module docstring for justification) -----------------
SIGMA_FORM = 1.0    # strokes/round: persistent within-week form (correlates rounds)
SIGMA_ROUND = 2.6   # strokes/round: independent round-to-round noise
ROUNDS = 4
DEFAULT_SIMS = 25_000
DEFAULT_CUT_LINE = 65


def simulate(players, sims, cut_line, sigma_form, sigma_round, seed=None):
    """Run the Monte Carlo. Uses numpy if available, else a pure-Python fallback
    (slower but zero-dependency, so the weekly cloud run never breaks on a missing
    package). Both paths implement the identical model. Returns a list of
    per-player result dicts sorted by win probability."""
    if HAVE_NUMPY:
        return _simulate_numpy(players, sims, cut_line, sigma_form, sigma_round, seed)
    return _simulate_python(players, sims, cut_line, sigma_form, sigma_round, seed)


def _format_results(players, skill, wins, top5, top10, top20, made, finish_sum, sims):
    """Shared result assembly for both backends. All count args are per-player lists."""
    results = []
    for i, p in enumerate(players):
        mc = made[i]
        results.append(
            {
                "name": p["name"],
                "skill": round(float(skill[i]), 3),
                "win_pct": round(100.0 * wins[i] / sims, 2),
                "top5_pct": round(100.0 * top5[i] / sims, 2),
                "top10_pct": round(100.0 * top10[i] / sims, 2),
                "top20_pct": round(100.0 * top20[i] / sims, 2),
                "make_cut_pct": round(100.0 * mc / sims, 1),
                "exp_finish": round(finish_sum[i] / mc, 1) if mc > 0 else None,
                "notes": p.get("notes", ""),
            }
        )
    results.sort(key=lambda r: r["win_pct"], reverse=True)
    return results


def _simulate_numpy(players, sims, cut_line, sigma_form, sigma_round, seed=None):
    rng = np.random.default_rng(seed)
    n = len(players)

    skill = np.array(
        [p["skill"] + p.get("adjustment", 0.0) for p in players], dtype=float
    )  # (n,)

    # Per-sim, per-player persistent form (one draw per simulated week).
    form = rng.normal(0.0, sigma_form, size=(sims, n))          # (sims, n)

    # Independent round noise for all 4 rounds at once.
    noise = rng.normal(0.0, sigma_round, size=(sims, n, ROUNDS))  # (sims, n, ROUNDS)

    # Per-round performance (SG): skill + form (broadcast over rounds) + noise.
    perf = skill[None, :, None] + form[:, :, None] + noise        # (sims, n, ROUNDS)

    two_round = perf[:, :, :2].sum(axis=2)   # (sims, n) — 36-hole total SG
    full = perf.sum(axis=2)                  # (sims, n) — 72-hole total SG

    # --- Cut: keep top `cut_line` + ties per sim --------------------------------
    if cut_line and 0 < cut_line < n:
        # Threshold = the cut_line-th best 36-hole score in each sim.
        # Higher SG is better, so we want the cut_line-th largest value per row.
        part = np.partition(two_round, n - cut_line, axis=1)
        threshold = part[:, n - cut_line][:, None]               # (sims, 1)
        made_cut = two_round >= threshold                         # (sims, n) bool
    else:
        made_cut = np.ones((sims, n), dtype=bool)

    # Missed-cut players can't win or place: push their 72-hole total to -inf.
    full_eff = np.where(made_cut, full, -np.inf)

    # --- Rankings (1 = best) ----------------------------------------------------
    # argsort descending, then invert the permutation to get each player's rank.
    order = np.argsort(-full_eff, axis=1)                         # (sims, n)
    ranks = np.empty_like(order)
    rows = np.arange(sims)[:, None]
    ranks[rows, order] = np.arange(1, n + 1)[None, :]            # rank per player

    # Missed-cut players get a sentinel finish so they don't pollute "best finish".
    ranks_made = np.where(made_cut, ranks, n + 1)

    wins = (ranks == 1).sum(axis=0)
    top5 = (ranks_made <= 5).sum(axis=0)
    top10 = (ranks_made <= 10).sum(axis=0)
    top20 = (ranks_made <= 20).sum(axis=0)
    made_cut_count = made_cut.sum(axis=0)
    # Sum of finishing positions over sims where the player made the cut.
    finish_sum = np.where(made_cut, ranks, 0).sum(axis=0)

    return _format_results(
        players, skill, wins, top5, top10, top20,
        made_cut_count, finish_sum, sims,
    )


def _simulate_python(players, sims, cut_line, sigma_form, sigma_round, seed=None):
    """Zero-dependency fallback. Same model as the numpy path, just slower."""
    import random

    rng = random.Random(seed)
    gauss = rng.gauss
    n = len(players)
    skill = [p["skill"] + p.get("adjustment", 0.0) for p in players]

    wins = [0] * n
    top5 = [0] * n
    top10 = [0] * n
    top20 = [0] * n
    made_cut_count = [0] * n
    finish_sum = [0] * n

    do_cut = bool(cut_line) and 0 < cut_line < n

    for _ in range(sims):
        # 36-hole and 72-hole SG totals per player for this simulated tournament.
        two = [0.0] * n
        full = [0.0] * n
        for i in range(n):
            base = skill[i] + gauss(0.0, sigma_form)  # skill + persistent week form
            r1 = base + gauss(0.0, sigma_round)
            r2 = base + gauss(0.0, sigma_round)
            r3 = base + gauss(0.0, sigma_round)
            r4 = base + gauss(0.0, sigma_round)
            two[i] = r1 + r2
            full[i] = r1 + r2 + r3 + r4

        if do_cut:
            cut_val = sorted(two, reverse=True)[cut_line - 1]  # cut_line-th best
            made = [two[i] >= cut_val for i in range(n)]
        else:
            made = [True] * n

        # Rank made-cut players by 72-hole total (higher = better; 1 = best).
        contenders = sorted(
            (i for i in range(n) if made[i]), key=lambda i: full[i], reverse=True
        )
        for pos, i in enumerate(contenders, 1):
            made_cut_count[i] += 1
            finish_sum[i] += pos
            if pos == 1:
                wins[i] += 1
            if pos <= 5:
                top5[i] += 1
            if pos <= 10:
                top10[i] += 1
            if pos <= 20:
                top20[i] += 1

    return _format_results(
        players, skill, wins, top5, top10, top20,
        made_cut_count, finish_sum, sims,
    )


def main():
    ap = argparse.ArgumentParser(description="PGA Monte Carlo simulator")
    ap.add_argument("field", help="path to field JSON")
    ap.add_argument("--sims", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=None, help="write results JSON here")
    args = ap.parse_args()

    with open(args.field) as f:
        cfg = json.load(f)

    players = cfg["players"]
    if not players:
        sys.exit("No players in field.")
    for p in players:
        if "skill" not in p:
            sys.exit(f"Player missing 'skill': {p.get('name', p)}")

    sims = args.sims or cfg.get("sims", DEFAULT_SIMS)
    cut_line = cfg.get("cut_line", DEFAULT_CUT_LINE)
    params = cfg.get("params", {})
    sigma_form = params.get("sigma_form", SIGMA_FORM)
    sigma_round = params.get("sigma_round", SIGMA_ROUND)

    results = simulate(
        players, sims, cut_line, sigma_form, sigma_round, seed=args.seed
    )

    out = {
        "event": cfg.get("event", "Unknown event"),
        "course": cfg.get("course", ""),
        "date": cfg.get("date", ""),
        "sims": sims,
        "cut_line": cut_line,
        "params": {"sigma_form": sigma_form, "sigma_round": sigma_round},
        "field_size": len(players),
        "results": results,
    }

    if args.out:
        with open(args.out, "w") as f:
            json.dump(out, f, indent=2)

    # Pretty console table (top 20 by win %).
    print(f"\n{out['event']}  —  {out['course']}  ({out['date']})")
    print(f"{sims:,} sims · field {len(players)} · cut {cut_line} · "
          f"σ_form={sigma_form} σ_round={sigma_round}\n")
    hdr = f"{'#':>3} {'Player':<26}{'Win%':>7}{'Top5':>7}{'Top10':>7}{'Top20':>7}{'Cut%':>7}{'ExpFin':>8}"
    print(hdr)
    print("-" * len(hdr))
    for rank, r in enumerate(results[:20], 1):
        ef = "-" if r["exp_finish"] is None else f"{r['exp_finish']:.1f}"
        print(f"{rank:>3} {r['name']:<26}{r['win_pct']:>7.2f}{r['top5_pct']:>7.2f}"
              f"{r['top10_pct']:>7.2f}{r['top20_pct']:>7.2f}{r['make_cut_pct']:>7.1f}{ef:>8}")
    print()


if __name__ == "__main__":
    main()
