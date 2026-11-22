"""Searching published sources for a phrase, for the external-source
similarity check (``application/integrity/external``).

The one service wired in is CORE (core.ac.uk), the open-access research
aggregator, whose API returns full texts. It needs an API key (free for
institutions), read from ``CORE_API_KEY`` or the owner-only file
``var/secrets/core_api_key``. Only short phrases from the student's work are
sent, never the whole text, and only when an integrity setting allows it.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

CORE_SEARCH = "https://api.core.ac.uk/v3/search/works"
TIMEOUT = 20
MAX_TEXT = 400_000
HITS_PER_PHRASE = 3


class ExternalSearchError(Exception):
    """The service could not be reached or refused the request."""


def core_key() -> str:
    key = os.environ.get("CORE_API_KEY", "").strip()
    if key:
        return key
    from education_system.paths import UNIVERSITY_INTEGRITY_CORE_KEY_FILE
    try:
        return UNIVERSITY_INTEGRITY_CORE_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_core_key(key) -> str:
    """Write the key to the owner-only secrets file. Returns its path."""
    from education_system.paths import UNIVERSITY_INTEGRITY_CORE_KEY_FILE as path
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(str(key).strip())
    os.chmod(path, 0o600)
    return str(path)


def configured() -> bool:
    return bool(core_key())


def search(phrase) -> list[dict]:
    """Works whose full text contains ``phrase``: ``[{"title", "url", "text"}]``."""
    key = core_key()
    if not key:
        raise ExternalSearchError("No external search service is set up (CORE API key missing)")
    query = urllib.parse.urlencode({"q": f'"{phrase}"', "limit": HITS_PER_PHRASE})
    request = urllib.request.Request(f"{CORE_SEARCH}?{query}",
                                     headers={"Authorization": f"Bearer {key}",
                                              "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # nosec B310 - fixed https URL
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise ExternalSearchError(f"CORE refused the search (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ExternalSearchError(f"CORE could not be reached: {exc}") from None
    found = []
    for work in data.get("results") or []:
        text = work.get("fullText") or ""
        if not text.strip():
            continue
        url = work.get("downloadUrl") or ""
        if not url:
            links = work.get("links") or []
            url = next((link.get("url") for link in links if link.get("url")), "")
        if not url and work.get("doi"):
            url = f"https://doi.org/{work['doi']}"
        found.append({"title": (work.get("title") or "Untitled work")[:300], "url": url,
                      "text": text[:MAX_TEXT]})
    return found
