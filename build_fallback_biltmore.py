#!/usr/bin/env python3
"""
Fallback: build Biltmore Championship Asheville field from Wyndham Championship
(2026-08-06) cached data. Used when the DataGolf API is blocked by egress policy.

Limitations:
- Field is Wyndham Championship roster (standard fall event approximation)
- No Cliffs at Walnut Cove course-fit adjustments (zeroed out)
- Market odds from Wyndham are nulled (wrong event)
- Skill data current as of Wyndham last_updated
"""
import json, os

SRC_FIELD = "runs/field_2026-08-06.json"
SRC_DG    = "runs/dg_2026-08-06.json"
OUT_DATE  = "2026-09-17"
EVENT     = "Biltmore Championship Asheville (est. — API unavailable)"
COURSE    = "The Cliffs at Walnut Cove, Arden, NC"
CUT_LINE  = 65

src_field = json.load(open(SRC_FIELD))
src_dg    = json.load(open(SRC_DG))

players_field = []
for p in src_field["players"]:
    players_field.append({
        "name": p["name"],
        "skill": p["skill"],
        "adjustment": 0.0,
        "notes": f"skill from DG ({src_dg['last_updated']}), no Walnut Cove course-fit applied",
    })

field_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "cut_line": CUT_LINE,
    "source": f"DataGolf API unavailable (egress blocked); skill from {SRC_FIELD} ({src_dg['last_updated']}); no course-fit",
    "players": players_field,
}

players_dg = []
for p in src_dg["players"]:
    players_dg.append({
        "name": p["name"],
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
    "source_note": "DataGolf API blocked by egress policy. Skill ratings from Wyndham Championship roster (2026-08-06). No Walnut Cove fit. Market odds nulled.",
    "players": players_dg,
}

os.makedirs("runs", exist_ok=True)
json.dump(field_out, open(f"runs/field_{OUT_DATE}.json", "w"), indent=2)
json.dump(dg_out,   open(f"runs/dg_{OUT_DATE}.json",    "w"), indent=2)

print(f"Wrote runs/field_{OUT_DATE}.json  ({len(players_field)} players, cut {CUT_LINE})")
print(f"Wrote runs/dg_{OUT_DATE}.json")
print(f"Source skill data: {src_dg['last_updated']}")
print("WARNING: Field is Wyndham Championship roster (not exact Biltmore Championship field). No Walnut Cove course-fit applied.")
