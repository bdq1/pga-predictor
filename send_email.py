#!/usr/bin/env python3
"""
Send an email. Two backends, auto-selected:

  * Resend HTTP API  — used when RESEND_API_KEY is set. HTTPS, so it works inside
    the cloud routine sandbox (where outbound SMTP is blocked).
  * Gmail SMTP        — fallback for local use when no Resend key is present.

Environment variables:
  RESEND_API_KEY     enables the Resend backend (https://resend.com, free tier)
  RESEND_FROM        sender for Resend; default "onboarding@resend.dev" (works
                     without domain verification, but can only deliver to the email
                     you registered your Resend account with). Set to a verified
                     domain address once bdq.be is verified.
  GMAIL_ADDRESS      SMTP sender (fallback backend)
  GMAIL_APP_PASSWORD 16-char Google App Password (fallback backend)
  REPORT_TO          recipient; defaults to GMAIL_ADDRESS

Usage:
  set -a; . ./.env; set +a
  python3 send_email.py --subject "..." --html runs/email_2026-06-04.html \
                        --text runs/email_2026-06-04.txt [--to bruno@bdq.be]
"""

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_resend(api_key, sender, recipient, subject, html, text):
    payload = json.dumps({
        "from": sender, "to": [recipient], "subject": subject,
        "html": html, "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 # Cloudflare in front of api.resend.com blocks the default
                 # "Python-urllib/x" UA (403 error 1010); send a normal one.
                 "User-Agent": "pga-predictor/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
        print(f"Sent via Resend ('{subject}') to {recipient} — id {body.get('id')}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Resend send failed: HTTP {e.code} — {e.read().decode()[:300]}")


def send_smtp(sender, pwd, recipient, subject, html, text):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(sender, pwd)
        s.sendmail(sender, [recipient], msg.as_string())
    print(f"Sent via Gmail SMTP ('{subject}') to {recipient}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--html", required=True, help="path to HTML body file")
    ap.add_argument("--text", help="path to plain-text body file (fallback)")
    ap.add_argument("--to", help="recipient; default REPORT_TO or sender")
    args = ap.parse_args()

    html = open(args.html).read()
    text = open(args.text).read() if args.text and os.path.exists(args.text) else \
        "This report requires an HTML-capable email client."

    resend_key = os.environ.get("RESEND_API_KEY")
    gmail = os.environ.get("GMAIL_ADDRESS")
    recipient = args.to or os.environ.get("REPORT_TO") or gmail
    if not recipient:
        sys.exit("No recipient: set REPORT_TO (or --to, or GMAIL_ADDRESS).")

    if resend_key:
        sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
        send_resend(resend_key, sender, recipient, args.subject, html, text)
    elif gmail and os.environ.get("GMAIL_APP_PASSWORD"):
        send_smtp(gmail, os.environ["GMAIL_APP_PASSWORD"], recipient,
                  args.subject, html, text)
    else:
        sys.exit("No email backend configured. Set RESEND_API_KEY, or "
                 "GMAIL_ADDRESS + GMAIL_APP_PASSWORD.")


if __name__ == "__main__":
    main()
