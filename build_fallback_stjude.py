#!/usr/bin/env python3
"""
Fallback: build a FedEx St. Jude Championship field from the most recent cached DataGolf data.
Used when the DataGolf API is blocked by egress policy.

Limitations:
- Field approximated from Wyndham Championship roster, filtered to top ~70 by DG skill rank
  (actual field is top 70 FedEx Cup points leaders, which may differ)
- No TPC Southwind course-fit adjustments (zeroed out)
- Market odds from prior event are nulled (wrong event)
- No-cut event (cut_line=0): all players simulate the full 72 holes
- Skill data current as of last_updated from source file
"""
import json, os

SRC_FIELD = "runs/field_2026-08-07.json"
SRC_DG    = "runs/dg_2026-08-07.json"
OUT_DATE  = "2026-08-13"
EVENT     = "FedEx St. Jude Championship (est. — API unavailable)"
COURSE    = "TPC Southwind, Memphis TN"
CUT_LINE  = 0   # no-cut FedEx Cup Playoffs event (~70-player field)
FIELD_SIZE = 70  # approximate FedEx St. Jude field size

src_field = json.load(open(SRC_FIELD))
src_dg    = json.load(open(SRC_DG))

# Index source by name
field_by_name = {p["name"]: p for p in src_field["players"]}
dg_by_name    = {p["name"]: p for p in src_dg["players"]}

# Sort by datagolf_rank first, then baseline_pred descending as tiebreak
# to approximate FedEx Cup qualification order
def sort_key(p):
    rank = p.get("datagolf_rank") or 9999
    skill = p.get("baseline_pred") or -99
    return (rank, -skill)

dg_sorted = sorted(src_dg["players"], key=sort_key)
top_players = dg_sorted[:FIELD_SIZE]

players_field = []
for p in top_players:
    name = p["name"]
    fp = field_by_name.get(name, {})
    players_field.append({
        "name": name,
        "skill": p.get("baseline_pred") or fp.get("skill", 0.0),
        "adjustment": 0.0,
        "notes": f"skill from DG ({src_dg['last_updated']}), no TPC Southwind course-fit applied",
    })

field_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "cut_line": CUT_LINE,
    "source": (
        f"DataGolf API unavailable (egress blocked); "
        f"skill from {SRC_FIELD} ({src_dg['last_updated']}); "
        f"field approx. top {FIELD_SIZE} by DG rank; no course-fit"
    ),
    "players": players_field,
}

players_dg = []
for p in top_players:
    name = p["name"]
    players_dg.append({
        "name": name,
        "dg_id": p.get("dg_id"),
        "baseline_pred": p.get("baseline_pred"),
        "final_pred": p.get("baseline_pred"),
        "adjustment": 0.0,
        "std_deviation": p.get("std_deviation"),
        "total_course_history_adjustment": 0.0,
        "total_fit_adjustment": 0.0,
        "dg_win": None,
        "dg_top5": None,
        "dg_top10": None,
        "dg_top20": None,
        "dg_make_cut": None,
        "mkt_win_odds": None,
        "mkt_win_prob": None,
        "sg_total": p.get("sg_total"),
        "sg_ott": p.get("sg_ott"),
        "sg_app": p.get("sg_app"),
        "sg_arg": p.get("sg_arg"),
        "sg_putt": p.get("sg_putt"),
        "driving_dist": p.get("driving_dist"),
        "driving_acc": p.get("driving_acc"),
        "owgr_rank": p.get("owgr_rank"),
        "datagolf_rank": p.get("datagolf_rank"),
    })

dg_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "last_updated": src_dg.get("last_updated"),
    "source_note": (
        "DataGolf API blocked by egress policy. "
        f"Skill ratings from Wyndham Championship roster (2026-08-07). "
        f"Field approximated as top {FIELD_SIZE} by DataGolf rank. "
        "No TPC Southwind fit. Market odds nulled. No-cut event."
    ),
    "players": players_dg,
}

os.makedirs("runs", exist_ok=True)
json.dump(field_out, open(f"runs/field_{OUT_DATE}.json", "w"), indent=2)
json.dump(dg_out,   open(f"runs/dg_{OUT_DATE}.json",    "w"), indent=2)

print(f"Wrote runs/field_{OUT_DATE}.json  ({len(players_field)} players, cut {CUT_LINE})")
print(f"Wrote runs/dg_{OUT_DATE}.json")
print(f"Source skill data: {src_dg['last_updated']}")
print(f"WARNING: Field is estimated top {FIELD_SIZE} by DG rank from Wyndham roster.")
print("WARNING: No TPC Southwind course-fit applied. No-cut event (cut_line=0).")
