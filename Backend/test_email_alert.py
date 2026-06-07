"""
test_email_alert.py — Quick check that email alerts actually deliver.

Run from the Backend folder:
    python3 test_email_alert.py

It loads your .env, prints the config, then sends ONE real test email
synchronously so you see a clear PASS/FAIL with the exact SMTP error if any.
"""
from dotenv import load_dotenv
load_dotenv()

import telegram_alerts as ta


def main():
    print("── Email alert config ─────────────────────────────")
    print(f"  SMTP_HOST     : {ta.SMTP_HOST}:{ta.SMTP_PORT}")
    print(f"  FROM (sender) : {ta.ALERT_EMAIL_FROM or '(empty!)'}")
    print(f"  TO (recipient): {ta.ALERT_EMAIL_TO or '(empty!)'}")
    print(f"  App password  : {'set (' + str(len(ta.ALERT_EMAIL_APP_PASSWORD)) + ' chars)' if ta.ALERT_EMAIL_APP_PASSWORD else '(empty!)'}")
    print(f"  EMAIL_ENABLED : {ta.EMAIL_ENABLED}")
    print("───────────────────────────────────────────────────")

    if not ta.EMAIL_ENABLED:
        print("\n✗ Email is DISABLED — set ALERT_EMAIL_FROM and ALERT_EMAIL_APP_PASSWORD in .env.")
        return

    print(f"\nSending a test email to {ta.ALERT_EMAIL_TO} ...\n")

    subject = ta._build_subject("Email Test", "INFO")
    body    = ta._build_message(
        title          = "Email Test",
        message        = "This is a test alert from PlantMind AI. If you can read this, email alerts work!",
        severity       = "INFO",
        component      = "Email System",
        current_value  = None,
        allowed_range  = None,
        action_taken   = "Sent a test email",
        recommendation = "No action needed — this is only a test.",
        data           = {"Test": "OK", "Sent at": "now"},
    )

    # Call the sender SYNCHRONOUSLY so we get the real result / error here.
    ta._send_email_safe(subject, body, "INFO", "Email Test")

    print("\nIf you saw a line starting with '[Email] Sent' above → PASS. "
          "Check the inbox (and Spam) of", ta.ALERT_EMAIL_TO)
    print("If you saw '[Email] ERROR' → read the message; it is the exact SMTP failure reason.")


if __name__ == "__main__":
    main()
