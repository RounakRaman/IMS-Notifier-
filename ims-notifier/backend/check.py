"""
Entry point for the daily cron job. Runs once per invocation:
  1. Fetch IMS notifications page
  2. Filter by the keywords stored in the DB
  3. For any match NOT already seen, mark it seen and queue for delivery
  4. Send one email containing all new matches, and one push per match

Run manually:   python check.py
Run on Render:  configured as a Cron Job pointing to this script
"""

import logging
import sys

from db import init_db, list_keywords, is_seen, mark_seen
from scraper import fetch_notifications, filter_by_keywords
from notifier import send_email, send_push


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    log = logging.getLogger("check")

    init_db()

    keywords = list_keywords()
    if not keywords:
        log.info("No keywords configured. Exiting cleanly.")
        return 0

    log.info("Checking IMS with keywords: %s", keywords)

    try:
        all_notifs = fetch_notifications()
    except Exception as e:
        log.exception("Failed to fetch IMS page: %s", e)
        return 2

    matches = filter_by_keywords(all_notifs, keywords)
    log.info("Total notifications: %d, keyword matches: %d", len(all_notifs), len(matches))

    new_matches = []
    for n in matches:
        if is_seen(n.hash_id):
            continue
        # Figure out which keyword matched (for logging / display)
        text_lower = (n.text + " " + (n.link or "")).lower()
        matched_kw = next((k for k in keywords if k.lower() in text_lower), "")
        mark_seen(n.hash_id, n.date, n.text, n.link, matched_kw)
        new_matches.append(n)

    if not new_matches:
        log.info("No new matches. Nothing to send.")
        return 0

    log.info("Sending notifications for %d new matches", len(new_matches))
    send_email(new_matches)
    send_push(new_matches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
