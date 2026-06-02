#!/usr/bin/env python3
"""
Send an email via Gmail SMTP (TLS). Reads credentials from the environment:

  GMAIL_ADDRESS        the sending Gmail account, e.g. bruno@bdq.be
  GMAIL_APP_PASSWORD   a 16-char Google App Password (NOT your normal password)
                       create at https://myaccount.google.com/apppasswords
  REPORT_TO            (optional) recipient; defaults to GMAIL_ADDRESS

Works locally now and unchanged inside the weekly cloud routine (set the same
vars as secrets there). Standard library only.

Usage:
  set -a; . ./.env; set +a
  python3 send_email.py --subject "..." --html runs/email_2026-06-04.html \
                        --text runs/email_2026-06-04.txt [--to bruno@bdq.be]
"""

import argparse
import os
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--html", required=True, help="path to HTML body file")
    ap.add_argument("--text", help="path to plain-text body file (fallback)")
    ap.add_argument("--to", help="recipient; default REPORT_TO or sender")
    args = ap.parse_args()

    sender = os.environ.get("GMAIL_ADDRESS")
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender or not pwd:
        sys.exit("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD (see .env / app passwords).")
    recipient = args.to or os.environ.get("REPORT_TO") or sender

    html = open(args.html).read()
    text = open(args.text).read() if args.text and os.path.exists(args.text) else \
        "This report requires an HTML-capable email client."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = args.subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(sender, pwd)
        s.sendmail(sender, [recipient], msg.as_string())
    print(f"Sent '{args.subject}' to {recipient}")


if __name__ == "__main__":
    main()
