"""Best-effort word counting for submitted files.

Returns ``None`` when a format cannot be read, so the caller can ask the
marker for a count instead of silently recording zero.
"""
import logging
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_PLAIN_TEXT = {".txt", ".md", ".rtf", ".csv", ".tex", ".html", ".htm"}
_WORD = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’-][A-Za-z0-9À-ɏ]+)*")


def count_text(text):
    return len(_WORD.findall(text or ""))


def _docx_text(path):
    # Read document.xml directly so python-docx is not a hard dependency.
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", " ", xml)


def _pdf_text(path):
    from pypdf import PdfReader  # optional dependency
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def count_words(file_path):
    """Word count of a submitted file, or ``None`` if it cannot be read."""
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    try:
        if suffix in _PLAIN_TEXT:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if suffix in {".html", ".htm"}:
                text = re.sub(r"<[^>]+>", " ", text)
            return count_text(text)
        if suffix == ".docx":
            return count_text(_docx_text(path))
        if suffix == ".pdf":
            return count_text(_pdf_text(path))
    except Exception:
        logger.debug("Could not count words in %s", path, exc_info=True)
    return None
