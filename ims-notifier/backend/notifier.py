"""
Notification delivery: Gmail SMTP email + Firebase Cloud Messaging push.

Environment variables:
  SMTP_HOST           default: smtp.gmail.com
  SMTP_PORT           default: 587
  SMTP_USER           your Gmail address (the account that SENDS the email)
  SMTP_PASSWORD       Gmail App Password (16 chars, no spaces)
  EMAIL_TO            comma-separated recipients (e.g. raman.rounak@gmail.com)
  EMAIL_FROM_NAME     optional display name, default "IMS Notifier"

  FCM_SERVICE_ACCOUNT_JSON  full JSON of a Firebase service account (stringified)
                            If empty, push notifications are skipped.
"""

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import List

import requests

from db import list_device_tokens, unregister_device
from scraper import Notification

logger = logging.getLogger(__name__)


# Email
def _build_email_html(matches: List[Notification]) -> str:
    rows_html = []
    for n in matches:
        link_html = (
            f'<a href="{escape(n.link)}">{escape(n.link)}</a>' if n.link else "&mdash;"
        )
        rows_html.append(f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;vertical-align:top;white-space:nowrap;">{escape(n.date or "&mdash;")}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{escape(n.text)}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;word-break:break-all;">{link_html}</td>
        </tr>
        """)
    body_rows = "\n".join(rows_html)
    return f"""
    <html>
    <body style="font-family: -apple-system, system-ui, Segoe UI, sans-serif; color:#222;">
      <h2 style="margin-bottom:4px;">New IMS Notifications</h2>
      <p style="color:#555;margin-top:0;">{len(matches)} new match(es) on your keywords.</p>
      <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;border-top:2px solid #222;">
        <thead>
          <tr style="background:#f6f6f6;">
            <th align="left" style="padding:8px;">Date</th>
            <th align="left" style="padding:8px;">Notification</th>
            <th align="left" style="padding:8px;">Link</th>
          </tr>
        </thead>
        <tbody>
          {body_rows}
        </tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:24px;">
        Source: https://www.imsnsit.org/imsnsit/notifications.php
      </p>
    </body>
    </html>
    """


def send_email(matches: List[Notification]) -> bool:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    email_to_raw = os.environ.get("EMAIL_TO", "").strip()
    from_name = os.environ.get("EMAIL_FROM_NAME", "IMS Notifier")

    if not (smtp_user and smtp_pass and email_to_raw):
        logger.warning("SMTP not configured; skipping email")
        return False

    recipients = [r.strip() for r in email_to_raw.split(",") if r.strip()]
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[IMS] {len(matches)} new notification(s) matched"
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = ", ".join(recipients)

    text_lines = [f"{len(matches)} new IMS notification(s) matched your keywords:\n"]
    for n in matches:
        text_lines.append(f"- [{n.date}] {n.text}")
        if n.link:
            text_lines.append(f"  {n.link}")
    plain = "\n".join(text_lines)

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_email_html(matches), "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())
        logger.info("Sent email to %s", recipients)
        return True
    except Exception as e:
        logger.exception("Failed to send email: %s", e)
        return False


# Firebase Cloud Messaging push
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_access_token_cache = {"token": None, "exp": 0}


def _get_fcm_access_token() -> str:
    """
    Build a short-lived OAuth2 access token from the service-account JSON
    using a signed JWT. Kept dependency-light (google-auth does this too,
    but we inline it to keep the deploy slim).
    """
    import time
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    raw = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON not set")

    now = time.time()
    if _access_token_cache["token"] and _access_token_cache["exp"] > now + 60:
        return _access_token_cache["token"]

    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=[_FCM_SCOPE]
    )
    creds.refresh(Request())
    _access_token_cache["token"] = creds.token
    _access_token_cache["exp"] = creds.expiry.timestamp() if creds.expiry else now + 3000
    return creds.token


def _fcm_project_id() -> str:
    raw = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return ""
    return json.loads(raw).get("project_id", "")


def send_push(matches: List[Notification]) -> int:
    """
    Send a push to every registered device. We send one push per new
    notification so each is actionable (tappable to open the link).
    Returns number of pushes successfully delivered to FCM.
    """
    raw = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        logger.info("FCM not configured; skipping push")
        return 0

    tokens = list_device_tokens()
    if not tokens:
        logger.info("No registered devices; skipping push")
        return 0

    try:
        access_token = _get_fcm_access_token()
        project_id = _fcm_project_id()
    except Exception as e:
        logger.exception("Failed to get FCM access token: %s", e)
        return 0

    endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    delivered = 0
    for n in matches:
        title = f"IMS: {n.matched_keyword if hasattr(n, 'matched_keyword') else 'New notification'}"
        # matched_keyword isn't on the dataclass; derive a simple title instead
        title = "New IMS Notification"
        body = n.text[:180]
        if n.date:
            body = f"[{n.date}] {body}"

        for token in tokens:
            payload = {
                "message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": {
                        "date": n.date or "",
                        "text": n.text,
                        "link": n.link or "",
                        "hash_id": n.hash_id,
                    },
                    "android": {
                        "priority": "HIGH",
                        "notification": {
                            "channel_id": "ims_notifications",
                            "click_action": "OPEN_NOTIFICATION",
                        },
                    },
                }
            }
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    delivered += 1
                elif resp.status_code in (404, 403):
                    # Token invalid. Remove.
                    logger.info("Pruning invalid FCM token")
                    unregister_device(token)
                else:
                    logger.warning(
                        "FCM send failed for token (%s): %s", resp.status_code, resp.text[:300]
                    )
            except Exception as e:
                logger.warning("FCM request exception: %s", e)

    logger.info("Delivered %d FCM pushes", delivered)
    return delivered
