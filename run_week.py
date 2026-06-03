#!/usr/bin/env python3
"""
One-command weekly pipeline, for GitHub Actions (or any open-internet runner).

Computes this week's Thursday date automatically, then runs the full chain:
  fetch_datagolf -> simulate -> analyze -> build_email -> send_email

No AI judgment needed: the event/field come from the DataGolf API (it auto-targets
the upcoming PGA event) and the cut line is auto-picked from field size.

Env:
  DATAGOLF_API_KEY, RESEND_API_KEY, RESEND_FROM, REPORT_TO  (see send_email.py)
  FORCE_DATE   optional YYYY-MM-DD override for the date label
  DRY_RUN      if set (any value), do everything EXCEPT send the email (for testing)

Usage:  python run_week.py
"""

import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def upcoming_thursday():
    """Nearest Thursday on or after today (UTC date in CI). Thu = weekday 3."""
    today = datetime.date.today()
    return (today + datetime.timedelta(days=(3 - today.weekday()) % 7)).isoformat()


def run(*args, capture=False):
    print("+ python", *args, flush=True)
    r = subprocess.run([sys.executable, *args], cwd=HERE, check=True,
                       capture_output=capture, text=True)
    if capture:
        sys.stdout.write(r.stdout)
        return r.stdout.strip()
    return None


def main():
    date = os.environ.get("FORCE_DATE") or upcoming_thursday()
    print(f"=== Weekly PGA forecast for {date} ===", flush=True)

    run("fetch_datagolf.py", "--date", date)                       # auto cut-line
    run("simulate.py", f"runs/field_{date}.json",
        "--sims", "40000", "--seed", "7", "--out", f"runs/results_{date}.json")
    run("analyze.py", "--date", date)
    subject = run("build_email.py", "--date", date, capture=True)

    if os.environ.get("DRY_RUN"):
        print(f"DRY_RUN set — skipping send. Subject would be: {subject}")
    else:
        run("send_email.py", "--subject", subject,
            "--html", f"runs/email_{date}.html", "--text", f"runs/email_{date}.txt")

    # Emit the date for the CI step that commits the run history.
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"date={date}\n")
    print(f"=== done: {date} ===")


if __name__ == "__main__":
    main()
