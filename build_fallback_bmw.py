#!/usr/bin/env python3
"""
Fallback: build BMW Championship field from cached St. Jude (2026-08-13) data.
Used when the DataGolf API is blocked by egress policy.

Limitations:
- Field is top-50 from St. Jude roster by skill (approximates FedExCup standings)
- No Bellerive Country Club course-fit adjustments (zeroed out)
- Market odds from St. Jude are nulled (wrong event)
- cut_line = 0 (BMW Championship has no cut: 50-player field plays all 72 holes)
"""
import json, os

SRC_FIELD = "runs/field_2026-08-13.json"
SRC_DG    = "runs/dg_2026-08-13.json"
OUT_DATE  = "2026-08-20"
EVENT     = "BMW Championship (est. — API unavailable)"
COURSE    = "Bellerive Country Club, Town and Country, MO"
CUT_LINE  = 0   # no cut: 50-player field, all play 72 holes

src_field = json.load(open(SRC_FIELD))
src_dg    = json.load(open(SRC_DG))

# BMW Championship: top 50 in FedExCup standings. Approximate with top 50 by skill.
players_sorted = sorted(src_field["players"], key=lambda p: -p["skill"])[:50]
names_in_field = {p["name"] for p in players_sorted}

players_field = []
for p in players_sorted:
    players_field.append({
        "name": p["name"],
        "skill": p["skill"],
        "adjustment": 0.0,
        "notes": f"skill from DG ({src_dg['last_updated']}), no Bellerive course-fit applied",
    })

field_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "cut_line": CUT_LINE,
    "source": (
        f"DataGolf API unavailable (egress blocked); skill from {SRC_FIELD} "
        f"({src_dg['last_updated']}); top-50 by skill approx FedExCup standings; no course-fit"
    ),
    "players": players_field,
}

# Build dg sidecar — only players in the field
dg_by_name = {p["name"]: p for p in src_dg["players"]}

players_dg = []
for p in players_sorted:
    src = dg_by_name.get(p["name"], {})
    players_dg.append({
        "name": p["name"],
        "dg_id": src.get("dg_id"),
        "baseline_pred": src.get("baseline_pred"),
        "final_pred": src.get("baseline_pred"),
        "adjustment": 0.0,
        "std_deviation": src.get("std_deviation"),
        "total_course_history_adjustment": 0.0,
        "total_fit_adjustment": 0.0,
        "dg_win": None,
        "dg_top5": None,
        "dg_top10": None,
        "dg_top20": None,
        "dg_make_cut": None,
        "mkt_win_odds": None,
        "mkt_win_prob": None,
        "sg_total": src.get("sg_total"),
        "sg_ott": src.get("sg_ott"),
        "sg_app": src.get("sg_app"),
        "sg_arg": src.get("sg_arg"),
        "sg_putt": src.get("sg_putt"),
        "driving_dist": src.get("driving_dist"),
        "driving_acc": src.get("driving_acc"),
        "owgr_rank": src.get("owgr_rank"),
        "datagolf_rank": src.get("datagolf_rank"),
    })

dg_out = {
    "event": EVENT,
    "course": COURSE,
    "date": OUT_DATE,
    "last_updated": src_dg.get("last_updated"),
    "source_note": (
        "DataGolf API blocked by egress policy. Skill ratings from St. Jude "
        "roster (2026-08-13), top-50 by skill approximating FedExCup standings. "
        "No Bellerive fit. Market odds nulled."
    ),
    "players": players_dg,
}

os.makedirs("runs", exist_ok=True)
json.dump(field_out, open(f"runs/field_{OUT_DATE}.json", "w"), indent=2)
json.dump(dg_out,   open(f"runs/dg_{OUT_DATE}.json",    "w"), indent=2)
print(f"Wrote runs/field_{OUT_DATE}.json ({len(players_field)} players)")
print(f"Wrote runs/dg_{OUT_DATE}.json ({len(players_dg)} players)")
