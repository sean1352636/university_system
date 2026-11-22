"""Virus scan for uploaded work, using a ClamAV daemon when there is one.

``clean`` and ``infected`` come from the scanner; ``not_scanned`` means no
scanner could be reached, and is recorded so staff can see which work went
unscanned. Set ``CLAMD_SOCKET`` for a daemon on a non-standard socket.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

CLEAN, INFECTED, NOT_SCANNED = "clean", "infected", "not_scanned"
_warned = False


def _scanner():
    global _warned
    try:
        import pyclamd
        socket = os.environ.get("CLAMD_SOCKET")
        scanner = pyclamd.ClamdUnixSocket(socket) if socket else pyclamd.ClamdUnixSocket()
        if scanner.ping():
            return scanner
    except Exception:
        logger.debug("ClamAV unavailable", exc_info=True)
    if not _warned:
        logger.warning("No ClamAV daemon reachable: uploaded work is not being virus scanned")
        _warned = True
    return None


def scan_file(path, scanner=None) -> str:
    """The scan result for the file at ``path``."""
    scanner = scanner or _scanner()
    if scanner is None:
        return NOT_SCANNED
    try:
        with open(path, "rb") as handle:
            found = scanner.scan_stream(handle.read())
    except Exception:
        logger.warning("Virus scan of %s failed", path, exc_info=True)
        return NOT_SCANNED
    if found:
        logger.warning("Upload refused, virus scanner reported: %s", found)
        return INFECTED
    return CLEAN


def check_upload(path) -> str:
    """Scan and content-check an uploaded file before it is stored. Returns the
    scan result, or raises ``ValueError`` when it must be refused."""
    from education_system.systems.university.infrastructure.security.file_upload import (
        validate_upload,
    )
    with open(path, "rb") as handle:
        content = handle.read()
    outcome = validate_upload(os.path.basename(path), content, category="documents")
    if not outcome["valid"]:
        raise ValueError(f"File validation failed: {outcome['error']}")
    result = scan_file(path)
    if result == INFECTED:
        raise ValueError("The virus scanner flagged this file, so it wasn't submitted.")
    return result
