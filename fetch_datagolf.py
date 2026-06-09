#!/usr/bin/env python3
"""
Fetch real player data from the DataGolf API and build this week's field JSON
(plus a sidecar of DataGolf signals used by the contrarian analysis).

This replaces the hand-estimated skill layer with measured strokes-gained data.
The simulation engine (simulate.py) is unchanged — only the *inputs* improve.

Outputs (for event date <D>):
  runs/field_<D>.json   field for simulate.py:
                          skill      = DataGolf baseline_pred  (true skill, SG/round)
                          adjustment = final_pred - baseline_pred
                                       (course history + course fit + weather etc.,
                                        already expressed in strokes by DataGolf)
  runs/dg_<D>.json      sidecar consumed by analyze.py:
                          per-player DataGolf win/top5/top10/top20/cut probs (the
                          "market"), SG category breakdown, std_deviation, the full
                          fit-adjustment decomposition, OWGR vs DataGolf rank.

Requires DATAGOLF_API_KEY in the environment (load from .env).

Usage:
  set -a; . ./.env; set +a
  python3 fetch_datagolf.py --date 2026-06-04 --cut-line 50 [--out-dir runs]
"""

import argparse
import datetime
import json
import os
import sys
import urllib.request

BASE = "https://feeds.datagolf.com"


def _get(path, key, **params):
    params.update(file_format="json", key=key)
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}/{path}?{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status != 200:
            sys.exit(f"DataGolf {path} returned HTTP {r.status}")
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description="Build field JSON from DataGolf API")
    ap.add_argument("--date", required=True, help="event date YYYY-MM-DD (Thursday)")
    ap.add_argument("--cut-line", type=int, default=None,
                    help="36-hole cut (top N + ties). If omitted, auto-picked from field "
                         "size: >=100 players -> 65 (standard event), else -> 50 "
                         "(limited/signature/major field). Pass 0 for a no-cut event.")
    ap.add_argument("--out-dir", default="runs")
    ap.add_argument("--max-stale-days", type=float, default=4.0,
                    help="Abort if DataGolf's last_updated is older than this many days. "
                         "Guards against emailing last week's forecast when the new event's "
                         "model isn't published yet. Set 0 to disable.")
    args = ap.parse_args()

    key = os.environ.get("DATAGOLF_API_KEY")
    if not key:
        sys.exit("DATAGOLF_API_KEY not set. Run: set -a; . ./.env; set +a")

    # --- pull the four feeds (all auto-target the current upcoming PGA event) -----
    decomp = _get("preds/player-decompositions", key, tour="pga")

    # Staleness guard. DataGolf publishes the upcoming event's model Monday
    # afternoon / Tuesday. Run too early and the feed still serves LAST week's
    # event, which would otherwise be emailed as a duplicate with this week's date.
    # Refuse to proceed if the data is older than --max-stale-days.
    if args.max_stale_days:
        lu = (decomp.get("last_updated") or "").replace("UTC", "").strip()
        try:
            ts = datetime.datetime.strptime(lu, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=datetime.timezone.utc)
            age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
            if age > args.max_stale_days:
                sys.exit(
                    f"STALE DATA: DataGolf last_updated {lu} UTC is {age:.1f} days old "
                    f"(limit {args.max_stale_days}). The new event's model isn't out yet "
                    f"(feed still shows {decomp.get('event_name')!r}). Refusing to build a "
                    f"stale forecast — try again later.")
        except ValueError:
            print(f"  warning: couldn't parse last_updated {lu!r}; skipping staleness check")

    pre = _get("preds/pre-tournament", key, tour="pga", odds_format="percent")
    skills = _get("preds/skill-ratings", key, display="value")
    rankings = _get("preds/get-dg-rankings", key)
    odds = _get("betting-tools/outrights", key, tour="pga", market="win",
                odds_format="decimal")

    event = decomp.get("event_name", "Unknown event")
    course = decomp.get("course_name") or ""

    # index helpers keyed by DataGolf player id (dg_id)
    skill_by_id = {p["dg_id"]: p for p in skills["players"]}
    rank_by_id = {p["dg_id"]: p for p in rankings["rankings"]}
    # pre-tournament "market" probs: prefer the course-history-fit model
    pre_model = pre.get("baseline_history_fit") or pre.get("baseline") or []
    pre_by_id = {p["dg_id"]: p for p in pre_model}

    # --- real sportsbook win odds -> de-vigged market-implied probability --------
    # Consensus = mean decimal odds across the major books for each player; convert
    # to raw implied prob (1/odds); normalise across the field so they sum to 1
    # (strips the bookmaker overround / vig). This is the honest "market" line.
    BOOKS = ["bet365", "betmgm", "draftkings", "fanduel", "caesars", "pinnacle",
             "betway", "bovada", "williamhill", "betcris", "betonline", "unibet"]
    raw_by_id = {}
    for o in odds.get("odds", []):
        quotes = [o[b] for b in BOOKS if isinstance(o.get(b), (int, float)) and o[b] > 1]
        if quotes:
            consensus = sum(quotes) / len(quotes)
            raw_by_id[o["dg_id"]] = (consensus, 1.0 / consensus)
    vig_total = sum(p for _, p in raw_by_id.values()) or 1.0
    mkt_by_id = {dg: {"odds": round(c, 2), "prob": round(p / vig_total, 4)}
                 for dg, (c, p) in raw_by_id.items()}

    players = []        # for simulate.py
    sidecar = []        # for analyze.py
    for d in decomp["players"]:
        dg_id = d["dg_id"]
        name = d["player_name"]
        baseline = d["baseline_pred"]
        final = d["final_pred"]
        adjustment = round(final - baseline, 3)

        sk = skill_by_id.get(dg_id, {})
        rk = rank_by_id.get(dg_id, {})
        mk = pre_by_id.get(dg_id, {})

        players.append({
            "name": name,
            "skill": round(baseline, 3),
            "adjustment": adjustment,
            "notes": f"DG fit {adjustment:+.2f} "
                     f"(hist {d.get('total_course_history_adjustment', 0):+.2f}, "
                     f"fit {d.get('total_fit_adjustment', 0):+.2f})",
        })

        sidecar.append({
            "name": name,
            "dg_id": dg_id,
            "baseline_pred": round(baseline, 3),
            "final_pred": round(final, 3),
            "adjustment": adjustment,
            "std_deviation": d.get("std_deviation"),
            "total_course_history_adjustment": d.get("total_course_history_adjustment"),
            "total_fit_adjustment": d.get("total_fit_adjustment"),
            # DataGolf's own probabilities = the "market" benchmark (percent)
            "dg_win": mk.get("win"),
            "dg_top5": mk.get("top_5"),
            "dg_top10": mk.get("top_10"),
            "dg_top20": mk.get("top_20"),
            "dg_make_cut": mk.get("make_cut"),
            # real sportsbook win market (de-vigged consensus)
            "mkt_win_odds": mkt_by_id.get(dg_id, {}).get("odds"),
            "mkt_win_prob": mkt_by_id.get(dg_id, {}).get("prob"),
            # skill category breakdown (SG)
            "sg_total": sk.get("sg_total"),
            "sg_ott": sk.get("sg_ott"),
            "sg_app": sk.get("sg_app"),
            "sg_arg": sk.get("sg_arg"),
            "sg_putt": sk.get("sg_putt"),
            "driving_dist": sk.get("driving_dist"),
            "driving_acc": sk.get("driving_acc"),
            # rankings
            "owgr_rank": rk.get("owgr_rank"),
            "datagolf_rank": rk.get("datagolf_rank"),
        })

    # Auto cut-line by field size when not given: large fields are standard events
    # (top 65 + ties); small fields are limited/signature/major fields (top 50).
    # The exact cut barely moves win/top-10 odds; it mainly shapes make-cut %.
    cut_line = args.cut_line
    if cut_line is None:
        cut_line = 65 if len(players) >= 100 else 50
        print(f"  cut-line auto: {cut_line} (field size {len(players)})")

    field = {
        "event": event,
        "course": course,
        "date": args.date,
        "cut_line": cut_line,
        "source": "DataGolf API (player-decompositions + pre-tournament + skill-ratings)",
        "players": players,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    fpath = os.path.join(args.out_dir, f"field_{args.date}.json")
    spath = os.path.join(args.out_dir, f"dg_{args.date}.json")
    with open(fpath, "w") as f:
        json.dump(field, f, indent=2)
    with open(spath, "w") as f:
        json.dump({"event": event, "course": course, "date": args.date,
                   "last_updated": decomp.get("last_updated"),
                   "players": sidecar}, f, indent=2)

    print(f"{event}  —  {course or 'course n/a'}")
    print(f"  field:   {fpath}  ({len(players)} players, cut {cut_line})")
    print(f"  sidecar: {spath}")
    # quick sanity: top 5 by final_pred
    top = sorted(sidecar, key=lambda p: p["final_pred"], reverse=True)[:5]
    print("  top 5 by DataGolf final skill (skill+fit):")
    for p in top:
        print(f"    {p['name']:<24} skill {p['baseline_pred']:+.2f}  "
              f"fit {p['adjustment']:+.2f}  -> {p['final_pred']:+.2f}  "
              f"(DG win {100*(p['dg_win'] or 0):.1f}%)")


if __name__ == "__main__":
    main()
