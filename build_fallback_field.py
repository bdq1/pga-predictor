#!/usr/bin/env python3
"""
Fallback: build a 3M Open field from the most recent cached DataGolf data.
Used when the DataGolf API is blocked by egress policy.

Limitations noted in output:
- Field is from The Open Championship roster (not the exact 3M Open field)
- No TPC Twin Cities course-fit adjustments (zeroed out)
- Market odds from The Open are nulled (would be wrong for 3M Open)
- Skill data current as of the last_updated timestamp in the source file
"""
import json, os

SRC_FIELD = "runs/field_2026-07-17.json"
SRC_DG    = "runs/dg_2026-07-17.json"
OUT_DATE  = "2026-07-24"
EVENT     = "3M Open (est. — API unavailable)"
COURSE    = "TPC Twin Cities, Blaine MN"
CUT_LINE  = 65

src_field = json.load(open(SRC_FIELD))
src_dg    = json.load(open(SRC_DG))

# Build field for simulate.py: use baseline_pred as skill, adjustment=0
players_field = []
for p in src_field["players"]:
    players_field.append({
        "name": p["name"],
        "skill": p["skill"],        # baseline_pred — true measured skill, stable week-to-week
        "adjustment": 0.0,          # no TPC Twin Cities fit data available
        "notes": f"skill from DG ({src_dg['last_updated']}), no TPC course-fit applied",
    })

field_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "cut_line": CUT_LINE,
    "source": f"DataGolf API unavailable (egress blocked); skill from {SRC_FIELD} ({src_dg['last_updated']}); no course-fit",
    "players": players_field,
}

# Build dg sidecar for analyze.py: keep skill/rank data, null out market odds (stale) and course fits
players_dg = []
for p in src_dg["players"]:
    players_dg.append({
        "name": p["name"],
        "dg_id": p.get("dg_id"),
        "baseline_pred": p.get("baseline_pred"),
        "final_pred": p.get("baseline_pred"),   # same as baseline since no fit applied
        "adjustment": 0.0,
        "std_deviation": p.get("std_deviation"),
        "total_course_history_adjustment": 0.0,
        "total_fit_adjustment": 0.0,
        # DG win probs are for The Open — null them (wrong event)
        "dg_win": None,
        "dg_top5": None,
        "dg_top10": None,
        "dg_top20": None,
        "dg_make_cut": None,
        # Market odds from The Open — null them (wrong event)
        "mkt_win_odds": None,
        "mkt_win_prob": None,
        # Skill breakdown stays valid (stable skill ratings)
        "sg_total": p.get("sg_total"),
        "sg_ott": p.get("sg_ott"),
        "sg_app": p.get("sg_app"),
        "sg_arg": p.get("sg_arg"),
        "sg_putt": p.get("sg_putt"),
        "driving_dist": p.get("driving_dist"),
        "driving_acc": p.get("driving_acc"),
        # Rankings stay valid
        "owgr_rank": p.get("owgr_rank"),
        "datagolf_rank": p.get("datagolf_rank"),
    })

dg_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "last_updated": src_dg.get("last_updated"),
    "source_note": "DataGolf API blocked by egress policy. Skill ratings from The Open Championship roster (2026-07-07). No TPC Twin Cities fit. Market odds nulled.",
    "players": players_dg,
}

os.makedirs("runs", exist_ok=True)
json.dump(field_out, open(f"runs/field_{OUT_DATE}.json", "w"), indent=2)
json.dump(dg_out,   open(f"runs/dg_{OUT_DATE}.json",    "w"), indent=2)

print(f"Wrote runs/field_{OUT_DATE}.json  ({len(players_field)} players, cut {CUT_LINE})")
print(f"Wrote runs/dg_{OUT_DATE}.json")
print(f"Source skill data: {src_dg['last_updated']}")
print("WARNING: Field is The Open Championship roster (not exact 3M Open field). No course-fit applied.")
