"""
Scraper for https://www.imsnsit.org/imsnsit/notifications.php

The IMS page renders a plain HTML table of notifications. Each row typically has:
- Date
- Notification text (often with an embedded link/attachment)
- A link to a PDF or external page

We parse the table, normalize each row into a dict, and hash it so we can detect
"new" notifications on subsequent runs.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

IMS_URL = "https://www.imsnsit.org/imsnsit/notifications.php"
BASE_URL = "https://www.imsnsit.org/imsnsit/"

# A real browser UA. The IMS site occasionally blocks requests-default UAs.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass
class Notification:
    date: str
    text: str
    link: Optional[str]
    hash_id: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text or "").strip()


def _make_hash(date: str, text: str, link: Optional[str]) -> str:
    """Stable identifier for a notification row. Used to dedupe across runs."""
    payload = f"{date}||{text}||{link or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fetch_html(timeout: int = 30) -> str:
    resp = requests.get(IMS_URL, headers=HEADERS, timeout=timeout, verify=True)
    resp.raise_for_status()
    return resp.text


def parse_notifications(html: str) -> List[Notification]:
    """
    The IMS notifications page uses a table layout. Rows of interest contain
    at least a date-looking cell and a text cell, optionally with an <a href>.

    We are defensive here because the IMS site has historically changed its
    HTML in minor ways, so we use heuristic parsing rather than brittle
    selectors tied to specific class names.
    """
    soup = BeautifulSoup(html, "html.parser")

    notifications: List[Notification] = []
    seen_hashes = set()

    # Strategy 1: iterate every <tr>, look for rows with a date-ish cell.
    date_pattern = re.compile(r"\b\d{1,2}[-/ ](?:\d{1,2}|[A-Za-z]{3,9})[-/ ]\d{2,4}\b")

    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        row_text = _clean(tr.get_text(" "))
        if not row_text or len(row_text) < 5:
            continue

        date_match = date_pattern.search(row_text)
        date_str = date_match.group(0) if date_match else ""

        # Text content: full row text minus date if present
        text = row_text
        if date_str:
            text = text.replace(date_str, "", 1).strip()
        text = _clean(text)

        # Link: first <a href> inside the row, if any
        link_tag = tr.find("a", href=True)
        link = None
        if link_tag:
            href = link_tag["href"].strip()
            if href and not href.startswith("#") and not href.lower().startswith("javascript:"):
                link = urljoin(BASE_URL, href)

        # Skip garbage rows (navigation, headers, empty)
        if len(text) < 10:
            continue
        lowered = text.lower()
        if lowered.startswith("s.no") or lowered.startswith("sr.") or "notification" == lowered:
            continue

        hash_id = _make_hash(date_str, text, link)
        if hash_id in seen_hashes:
            continue
        seen_hashes.add(hash_id)

        notifications.append(
            Notification(date=date_str, text=text, link=link, hash_id=hash_id)
        )

    logger.info("Parsed %d notifications from IMS page", len(notifications))
    return notifications


def fetch_notifications() -> List[Notification]:
    html = fetch_html()
    return parse_notifications(html)


def filter_by_keywords(
    notifications: List[Notification], keywords: List[str]
) -> List[Notification]:
    """
    Case-insensitive substring match on the notification text (and link URL).
    A notification matches if ANY keyword is present.
    """
    if not keywords:
        return []

    lowered_keywords = [k.lower().strip() for k in keywords if k and k.strip()]
    if not lowered_keywords:
        return []

    matched = []
    for n in notifications:
        haystack = (n.text + " " + (n.link or "")).lower()
        if any(kw in haystack for kw in lowered_keywords):
            matched.append(n)
    return matched


if __name__ == "__main__":
    # Manual smoke test
    logging.basicConfig(level=logging.INFO)
    notifs = fetch_notifications()
    print(f"Got {len(notifs)} notifications")
    for n in notifs[:5]:
        print(f"  [{n.date}] {n.text[:80]}...  link={n.link}")
