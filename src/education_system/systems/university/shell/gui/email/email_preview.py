"""Preview an e-mail in the branded design, in the web browser.

The page is built by ``smtp.build_message`` itself, so the preview is the
HTML part the recipient would get, not an approximation of it.
"""

from __future__ import annotations

import base64
import logging
import tempfile
import webbrowser
from pathlib import Path

from education_system.platform.delivery.gui.parented_dialogs import messagebox

logger = logging.getLogger(__name__)

SAMPLE_SUBJECT = "Assignment due soon: Research Methods Essay"
SAMPLE_BODY = """Dear Asha,

This is a reminder that your assignment is due in 2 day(s).

Assignment: Research Methods Essay
Module: CIS0001 - Computing Foundations
Due: 2026-11-04 23:59

Before you submit:
• Check your work against the marking criteria
• Confirm the own-work declaration
• Upload a PDF or Word file

Submission details
------------------
You can submit and check your receipt at https://portal.example.ac.uk/assignments.
Questions? E-mail the module team at modules@example.ac.uk.

Best regards,
Teaching and Learning Office"""


def html_for(subject: str, body: str) -> str:
    """The HTML part of the message as it would be sent."""
    from education_system.systems.university.infrastructure.email.smtp import build_message
    message = build_message(subject=subject, body=body, from_header="preview@localhost",
                            to_header="preview@localhost", styled=True)
    page, images = None, {}
    for part in message.walk():
        if part.get_content_type() == "text/html" and page is None:
            page = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        elif part.get_content_maintype() == "image" and part["Content-ID"]:
            images[part["Content-ID"].strip("<>")] = part
    if page is None:
        raise ValueError("This message has no HTML version")
    # A browser can't follow cid: links, so the preview carries the images.
    for cid, part in images.items():
        data = base64.b64encode(part.get_payload(decode=True)).decode("ascii")
        page = page.replace(f"cid:{cid}", f"data:{part.get_content_type()};base64,{data}")
    return page


def open_preview(parent, subject: str, body: str) -> str | None:
    """Write the page to a temporary file and open it; returns the path."""
    if not (body or "").strip():
        messagebox.showinfo("Preview", "Write the message first.", parent=parent)
        return None
    try:
        page = html_for(subject or "(no subject)", body)
        folder = Path(tempfile.gettempdir()) / "university-email-previews"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".html", prefix="preview-", dir=folder,
                                         delete=False, encoding="utf-8") as handle:
            handle.write(page)
        path = handle.name
    except Exception as exc:
        logger.exception("E-mail preview failed")
        messagebox.showerror("Preview", f"The preview couldn't be made: {exc}", parent=parent)
        return None
    if not webbrowser.open(Path(path).as_uri()):
        messagebox.showinfo("Preview", f"Open this file in a web browser:\n{path}",
                            parent=parent)
    return path


def open_sample(parent) -> str | None:
    """A sample message showing headings, details, lists, links and signature."""
    return open_preview(parent, SAMPLE_SUBJECT, SAMPLE_BODY)
