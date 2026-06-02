#!/usr/bin/env python3
"""
Build the two-part forecast from a completed sim + the DataGolf sidecar.

Part 1 — "The Favorites": straight Monte Carlo win probabilities (from results JSON).
Part 2 — "The Long Shots": four contrarian lenses, each mathematically grounded in
         real data, plus a synthesis of names that surface across multiple lenses.

Lenses
  1. Ceiling / boom-or-bust  — non-favorites with the biggest realistic upside,
       weighted by DataGolf's per-player volatility (std_deviation). Who can go low.
  2. Value vs market         — model win% minus the de-vigged sportsbook-implied
       win% (real books). Positive = the market is underpricing them. Cross-checked
       against DataGolf's own model so we can flag where the sharp model agrees.
  3. Form & course-fit tilt  — players the course/event most elevates, by DataGolf's
       fit adjustment (course history + course fit), independent of base skill.
  4. Model-vs-reputation gap — DataGolf skill rank vs OWGR. Big gap = the data rates
       them far above their reputation (or vice-versa).

Synthesis: a player appearing in >=2 lens shortlists is the strongest contrarian call.

Usage:  python3 analyze.py --date 2026-06-04 [--out-dir runs]
Writes runs/analysis_<date>.json and prints a readable summary.
"""

import argparse
import json
import os
import statistics


def nice(name):
    """DataGolf 'Last, First' -> 'First Last'."""
    if ", " in name:
        last, first = name.split(", ", 1)
        return f"{first} {last}"
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default="runs")
    ap.add_argument("--shortlist", type=int, default=6, help="rows per lens")
    args = ap.parse_args()

    d = args.date
    res = json.load(open(os.path.join(args.out_dir, f"results_{d}.json")))
    dg = json.load(open(os.path.join(args.out_dir, f"dg_{d}.json")))

    sim = {r["name"]: r for r in res["results"]}          # by DG name
    side = {p["name"]: p for p in dg["players"]}
    names = [r["name"] for r in res["results"]]            # sim order (by win%)

    win_rank = {n: i + 1 for i, n in enumerate(names)}     # 1 = our top favorite
    favorites = set(names[:5])                              # exclude from contrarian lists

    stds = [side[n]["std_deviation"] for n in names
            if side.get(n) and side[n].get("std_deviation")]
    median_std = statistics.median(stds) if stds else 1.0

    def row(n, **extra):
        r = sim[n]
        base = {"player": nice(n), "win": r["win_pct"], "top5": r["top5_pct"],
                "top10": r["top10_pct"], "make_cut": r["make_cut_pct"]}
        base.update(extra)
        return base

    # --- Lens 1: ceiling / boom-or-bust -----------------------------------------
    # Genuine DEEP longshots: restrict to players outside the top 10 in win odds,
    # then rank by their top-10 ceiling (best realistic-leaderboard probability).
    # DataGolf std_deviation is near-uniform across the field, so it can't drive a
    # volatility split here -- we surface upside among non-obvious names instead and
    # report std for transparency. "Who beyond the headline names can crack the top 10."
    CEIL_POOL = 10
    ceiling = []
    for n in names:
        if win_rank[n] <= CEIL_POOL or not side.get(n):
            continue
        std = side[n].get("std_deviation") or median_std
        ceiling.append(row(n, std=round(std, 2), win_rank=win_rank[n],
                           ceiling=sim[n]["top10_pct"]))
    ceiling.sort(key=lambda r: r["ceiling"], reverse=True)
    ceiling = ceiling[:args.shortlist]

    # --- Lens 2: value vs market -------------------------------------------------
    # edge = our win% - de-vigged market win%. Positive = market underprices.
    value = []
    for n in names:
        s = side.get(n)
        if not s or s.get("mkt_win_prob") is None:
            continue
        mkt = 100 * s["mkt_win_prob"]
        dgw = 100 * (s.get("dg_win") or 0)
        edge = sim[n]["win_pct"] - mkt
        value.append(row(n, mkt_win=round(mkt, 2), dg_win=round(dgw, 2),
                         edge=round(edge, 2), odds=s.get("mkt_win_odds"),
                         dg_agrees=(dgw - mkt) > 0.3))
    value.sort(key=lambda r: r["edge"], reverse=True)
    value = value[:args.shortlist]

    # --- Lens 3: form & course-fit tilt -----------------------------------------
    # DataGolf fit adjustment (course history + course fit), strokes/round.
    fit = []
    for n in names:
        s = side.get(n)
        if not s:
            continue
        adj = s.get("adjustment") or 0
        fit.append(row(n, fit=round(adj, 2),
                       hist=round(s.get("total_course_history_adjustment") or 0, 2),
                       coursefit=round(s.get("total_fit_adjustment") or 0, 2),
                       win_rank=win_rank[n]))
    fit.sort(key=lambda r: r["fit"], reverse=True)
    fit = fit[:args.shortlist]

    # --- Lens 4: model-vs-reputation gap ----------------------------------------
    # OWGR rank minus DataGolf rank. Large positive = data rates >> reputation.
    gap = []
    for n in names:
        s = side.get(n)
        if not s or not s.get("owgr_rank") or not s.get("datagolf_rank"):
            continue
        g = s["owgr_rank"] - s["datagolf_rank"]
        gap.append(row(n, owgr=s["owgr_rank"], dg_rank=s["datagolf_rank"], gap=g))
    gap.sort(key=lambda r: r["gap"], reverse=True)
    underrated = gap[:args.shortlist]

    # --- Synthesis: names appearing across multiple lenses -----------------------
    lens_members = {
        "ceiling": {r["player"] for r in ceiling},
        "value": {r["player"] for r in value},
        "fit": {r["player"] for r in fit},
        "underrated": {r["player"] for r in underrated},
    }
    counts = {}
    for lens, members in lens_members.items():
        for p in members:
            counts.setdefault(p, []).append(lens)
    synthesis = sorted(
        ({"player": p, "lenses": ls, "n": len(ls),
          "win": next((sim[k]["win_pct"] for k in sim if nice(k) == p), None)}
         for p, ls in counts.items() if len(ls) >= 2),
        key=lambda x: (x["n"], x["win"] or 0), reverse=True,
    )

    out = {
        "event": res["event"], "course": res["course"], "date": d,
        "sims": res["sims"], "cut_line": res["cut_line"],
        "favorites": [row(n, win_rank=win_rank[n]) for n in names[:15]],
        "long_shots": {
            "ceiling": ceiling, "value": value,
            "fit": fit, "underrated": underrated,
        },
        "synthesis": synthesis,
    }
    opath = os.path.join(args.out_dir, f"analysis_{d}.json")
    json.dump(out, open(opath, "w"), indent=2)

    # --- console summary ---------------------------------------------------------
    print(f"\n{out['event']} — {out['course']} ({d})  ·  {out['sims']:,} sims\n")
    print("PART 1 — THE FAVORITES (model win%)")
    for r in out["favorites"][:10]:
        print(f"  {r['win_rank']:>2}. {r['player']:<22} {r['win']:>5.1f}%  "
              f"top5 {r['top5']:>4.1f}  top10 {r['top10']:>4.1f}")

    print("\nPART 2 — THE LONG SHOTS")
    print(" [1] Deep longshots by top-10 ceiling (outside top-10 win odds):")
    for r in ceiling:
        print(f"     {r['player']:<22} top10 {r['ceiling']:>4.1f}%  top5 {r['top5']:>4.1f}  win {r['win']:.1f}% (win#{r['win_rank']})")
    print(" [2] Value vs market (our win% - de-vigged book%):")
    for r in value:
        flag = " <-- DG agrees" if r["dg_agrees"] else ""
        print(f"     {r['player']:<22} edge {r['edge']:+5.2f}  (us {r['win']:.1f} / mkt {r['mkt_win']:.1f} / DG {r['dg_win']:.1f})  @{r['odds']}{flag}")
    print(" [3] Form & course-fit tilt (DG fit strokes):")
    for r in fit:
        print(f"     {r['player']:<22} fit {r['fit']:+.2f}  (hist {r['hist']:+.2f} fit {r['coursefit']:+.2f})  win#{r['win_rank']}")
    print(" [4] Model-vs-reputation gap (OWGR - DG rank):")
    for r in underrated:
        print(f"     {r['player']:<22} OWGR {r['owgr']:>3} vs DG {r['dg_rank']:>3}  gap {r['gap']:+d}")

    print("\n SYNTHESIS — surface across multiple lenses:")
    if synthesis:
        for s in synthesis:
            print(f"     {s['player']:<22} {s['n']} lenses: {', '.join(s['lenses'])}  (win {s['win']:.1f}%)")
    else:
        print("     (no overlap this week)")
    print(f"\nwrote {opath}")


if __name__ == "__main__":
    main()
