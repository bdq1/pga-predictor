#!/usr/bin/env python3
"""
Render the two-part forecast email (HTML + plain text + subject) from the
analysis JSON produced by analyze.py. Pure formatting, no model logic.

Usage:  python3 build_email.py --date 2026-06-04 [--out-dir runs]
Writes runs/email_<date>.html and runs/email_<date>.txt, prints the subject.
"""

import argparse
import json
import os

GREEN = "#0a3d2e"
AMBER = "#7a3b00"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def fav_table(favs):
    rows = []
    for i, r in enumerate(favs[:12]):
        bg = "#eafaf2" if i == 0 else ("#f6f6f6" if i % 2 else "#ffffff")
        wt = "font-weight:600;" if i == 0 else ""
        rows.append(
            f'<tr style="text-align:right;background:{bg};{wt}">'
            f'<td style="padding:5px 8px;text-align:left">{r["win_rank"]}</td>'
            f'<td style="padding:5px 8px;text-align:left">{esc(r["player"])}</td>'
            f'<td>{r["win"]:.1f}</td><td>{r["top5"]:.1f}</td>'
            f'<td>{r["top10"]:.1f}</td><td>{r["make_cut"]:.0f}</td></tr>')
    return (
        '<table style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:8px">'
        f'<thead><tr style="background:{GREEN};color:#fff;text-align:right">'
        '<th style="padding:6px 8px;text-align:left">#</th>'
        '<th style="padding:6px 8px;text-align:left">Player</th>'
        '<th style="padding:6px 8px">Win%</th><th style="padding:6px 8px">Top5</th>'
        '<th style="padding:6px 8px">Top10</th><th style="padding:6px 8px">Cut%</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def value_table(value):
    head = ('<tr style="color:#888;text-align:right"><td style="text-align:left;padding:2px 6px">Player</td>'
            '<td style="padding:2px 6px">Edge</td><td style="padding:2px 6px">Us</td>'
            '<td style="padding:2px 6px">Mkt</td><td style="padding:2px 6px">DG</td>'
            '<td style="padding:2px 6px">Odds</td><td></td></tr>')
    rows = []
    for i, r in enumerate(value):
        bg = "background:#f6f6f6" if i % 2 else ""
        agree = '<span style="color:#197a2e">DG agrees</span>' if r.get("dg_agrees") else ""
        rows.append(
            f'<tr style="text-align:right;{bg}"><td style="text-align:left;padding:2px 6px">{esc(r["player"])}</td>'
            f'<td style="color:#197a2e;font-weight:600">{r["edge"]:+.1f}</td>'
            f'<td>{r["win"]:.1f}</td><td>{r["mkt_win"]:.1f}</td><td>{r["dg_win"]:.1f}</td>'
            f'<td>~{r["odds"]:.0f}</td><td style="padding-left:6px">{agree}</td></tr>')
    return ('<table style="border-collapse:collapse;width:100%;font-size:12.5px">'
            + head + "".join(rows) + '</table>')


def build(a):
    ev, course, date = a["event"], a["course"], a["date"]
    ls = a["long_shots"]

    def names(lst, fmt):
        return " · ".join(fmt(r) for r in lst)

    ceiling = names(ls["ceiling"], lambda r: f'{esc(r["player"])} <b>{r["ceiling"]:.1f}%</b>')
    fit = names(ls["fit"], lambda r: f'{esc(r["player"])} {r["fit"]:+.2f}'
                + (f' <span style="color:#888">(win#{r["win_rank"]})</span>' if r["win_rank"] > 10 else ""))
    rep = names(ls["underrated"], lambda r: f'{esc(r["player"])} <span style="color:#888">(OWGR {r["owgr"]}/DG {r["dg_rank"]})</span>')

    synth = a["synthesis"]
    synth_html = "".join(
        f'<b>{esc(s["player"])}</b> — {" + ".join(s["lenses"])} '
        f'<span style="color:#888">(win {s["win"]:.1f}%)</span><br>' for s in synth
    ) or '<span style="color:#888">No player surfaced across multiple lenses this week.</span>'

    html = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:700px">
<h2 style="margin:0 0 2px">PGA forecast — {esc(ev)}</h2>
<div style="color:#555;font-size:13.5px;margin-bottom:6px">{esc(course)} · <b>{esc(date)}</b> · {a['sims']:,} sims · cut top {a['cut_line']}+ties</div>
<div style="color:#555;font-size:12.5px;margin-bottom:16px;line-height:1.5">Skill inputs from the <b>DataGolf API</b> (measured strokes-gained + course-fit); value lens uses <b>real sportsbook odds, de-vigged</b>. Probabilities only — no betting advice.</div>
<h3 style="margin:0 0 8px;font-size:15px;color:{GREEN}">Part 1 — The Favorites</h3>
{fav_table(a['favorites'])}
<h3 style="margin:18px 0 8px;font-size:15px;color:{AMBER}">Part 2 — The Long Shots <span style="font-weight:400;font-size:12px;color:#888">(4 contrarian lenses)</span></h3>
<p style="font-size:13px;margin:0 0 4px"><b>① Deep ceiling</b> <span style="color:#888">— outside top-10 win odds, best top-10 upside</span><br>{ceiling}</p>
<p style="font-size:13px;margin:10px 0 4px"><b>② Value vs market</b> <span style="color:#888">— our win% − de-vigged sportsbook win%</span></p>
{value_table(ls['value'])}
<p style="font-size:13px;margin:10px 0 4px"><b>③ Course-fit tilt</b> <span style="color:#888">— DataGolf fit, strokes/round</span><br>{fit}</p>
<p style="font-size:13px;margin:10px 0 4px"><b>④ Model vs reputation</b> <span style="color:#888">— OWGR rank vs DataGolf skill rank</span><br>{rep}</p>
<div style="background:#fff7e6;border:1px solid #f0d488;border-radius:6px;padding:12px 14px;margin:16px 0 6px">
<div style="font-weight:700;font-size:13.5px;margin-bottom:6px;color:{AMBER}">★ Synthesis — names hitting multiple lenses (strongest contrarian signals)</div>
<div style="font-size:13px;line-height:1.7">{synth_html}</div></div>
<p style="font-size:11.5px;color:#777;border-top:1px solid #ddd;padding-top:10px;margin-top:14px;line-height:1.5">
<b>How to read this:</b> Monte Carlo probabilities on measured DataGolf skill + course-fit inputs; "market" is the de-vigged consensus of major sportsbooks. Even the favourite wins under 25% of the time. Model estimates, not certainties; no betting advice.</p>
</div>"""

    # plain-text fallback
    lines = [f"PGA forecast — {ev}", f"{course} · {date} · {a['sims']:,} sims · cut top {a['cut_line']}+ties", "",
             "PART 1 — THE FAVORITES (win%)"]
    for r in a["favorites"][:12]:
        lines.append(f"  {r['win_rank']:>2}. {r['player']:<22} {r['win']:>5.1f}%  (top5 {r['top5']:.1f}, top10 {r['top10']:.1f})")
    lines += ["", "PART 2 — THE LONG SHOTS",
              " [1] Deep ceiling: " + ", ".join(f"{r['player']} {r['ceiling']:.1f}%" for r in ls["ceiling"]),
              " [2] Value vs market: " + ", ".join(f"{r['player']} {r['edge']:+.1f} @{r['odds']:.0f}" for r in ls["value"]),
              " [3] Course-fit: " + ", ".join(f"{r['player']} {r['fit']:+.2f}" for r in ls["fit"]),
              " [4] Reputation gap: " + ", ".join(f"{r['player']} (OWGR {r['owgr']}/DG {r['dg_rank']})" for r in ls["underrated"]),
              "", " SYNTHESIS (multiple lenses): " + ("; ".join(f"{s['player']} [{'+'.join(s['lenses'])}]" for s in synth) or "none"),
              "", "Probabilities only. Even the favourite wins <25% of the time. No betting advice."]
    text = "\n".join(lines)

    subject = f"PGA forecast — {ev} ({date}): Favorites + Long Shots"
    return subject, html, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default="runs")
    args = ap.parse_args()
    a = json.load(open(os.path.join(args.out_dir, f"analysis_{args.date}.json")))
    subject, html, text = build(a)
    with open(os.path.join(args.out_dir, f"email_{args.date}.html"), "w") as f:
        f.write(html)
    with open(os.path.join(args.out_dir, f"email_{args.date}.txt"), "w") as f:
        f.write(text)
    print(subject)


if __name__ == "__main__":
    main()
