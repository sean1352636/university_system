"""Plain text from a submitted file: text and code files as they are,
PDF through ``pypdf``, Word through ``python-docx``; OpenDocument text and
slides (.odt/.odp), PowerPoint (.pptx) and RTF are read with the standard
library. HTML is kept as it is (it is compared as code). Anything else raises ``ValueError`` so the
caller can tell the user, rather than checking garbage bytes."""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

from education_system.systems.university.application.integrity import plagiarism_text

TEXT_TYPES = {"txt", "md", "csv", "tex"} | plagiarism_text.CODE_TYPES
OTHER_TYPES = ("pdf", "docx", "odt", "odp", "pptx", "rtf")
SUPPORTED = tuple(sorted(TEXT_TYPES)) + OTHER_TYPES
#: For file pickers.
FILETYPES = [("Documents", " ".join(f"*.{t}" for t in OTHER_TYPES + ("txt", "md"))),
             ("Code", " ".join(f"*.{t}" for t in sorted(plagiarism_text.CODE_TYPES))),
             ("All files", "*.*")]
MAX_BYTES = 25 * 1024 * 1024


def file_type(path) -> str:
    return Path(str(path)).suffix.lower().lstrip(".") or "txt"


def _pdf(path) -> str:
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _docx(path) -> str:
    import docx
    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        parts += [cell.text for row in table.rows for cell in row.cells]
    return "\n".join(parts)


_XML_TAG = re.compile(r"<[^>]+>")
_BREAKS = re.compile(r"</(?:text:p|text:h|a:p|w:p)>|<text:line-break/>|<text:tab/>")


def _xml_text(xml) -> str:
    xml = _BREAKS.sub("\n", xml)
    return html.unescape(_XML_TAG.sub("", xml))


def _opendocument(path) -> str:
    with zipfile.ZipFile(path) as zf:
        return _xml_text(zf.read("content.xml").decode("utf-8", errors="replace"))


def _pptx(path) -> str:
    with zipfile.ZipFile(path) as zf:
        slides = sorted((n for n in zf.namelist()
                         if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[-1]))
        parts = [_xml_text(zf.read(n).decode("utf-8", errors="replace")) for n in slides]
        notes = sorted(n for n in zf.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n))
        parts += [_xml_text(zf.read(n).decode("utf-8", errors="replace")) for n in notes]
    return "\n\n".join(parts)


_RTF_DEST = ("fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer",
             "listtable", "listoverridetable", "generator", "*")


def rtf_to_text(rtf) -> str:
    """The text of an RTF document: control words dropped, groups such as
    the font table skipped, \\par as a line break, \\'hh and \\uN decoded."""
    out, stack, skip = [], [], False
    i, n = 0, len(rtf)
    while i < n:
        ch = rtf[i]
        if ch == "{":
            stack.append(skip)
            i += 1
        elif ch == "}":
            skip = stack.pop() if stack else False
            i += 1
        elif ch == "\\":
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)", rtf[i:])
            if not m:
                i += 1
                continue
            word, arg, hexa, sym = m.groups()
            i += m.end()
            if skip:
                continue
            if hexa:
                out.append(bytes.fromhex(hexa).decode("cp1252", errors="replace"))
            elif sym:
                if sym == "*":
                    skip = True
                elif sym in "\\{}":
                    out.append(sym)
                elif sym == "~":
                    out.append(" ")
            elif word in _RTF_DEST:
                skip = True
            elif word in ("par", "line", "sect", "page"):
                out.append("\n")
            elif word == "tab":
                out.append("\t")
            elif word == "u" and arg:
                out.append(chr(int(arg) % 65536))
                if i < n and rtf[i] == "?":
                    i += 1
        else:
            if not skip and ch not in "\r\n":
                out.append(ch)
            i += 1
    return "".join(out)


def extract(path) -> str:
    from education_system.systems.university.infrastructure.stored_files import resolve
    path = resolve(path)
    if not path.is_file():
        raise ValueError(f"No such file: {path.name} (it is not at the stored path or in "
                         "the submissions folder)")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_BYTES // (1024 * 1024)} MB")
    kind = file_type(path)
    if kind in TEXT_TYPES:
        text = path.read_bytes().decode("utf-8", errors="replace")
    elif kind == "pdf":
        text = _pdf(path)
    elif kind == "docx":
        text = _docx(path)
    elif kind in ("odt", "odp"):
        text = _opendocument(path)
    elif kind == "pptx":
        text = _pptx(path)
    elif kind == "rtf":
        text = rtf_to_text(path.read_bytes().decode("latin-1", errors="replace"))
    else:
        raise ValueError(f"Text can't be read from .{kind} files; use PDF, Word (.docx), "
                         "OpenDocument (.odt), PowerPoint (.pptx), RTF or plain text")
    if not text.strip():
        raise ValueError(f"No text could be read from {path.name} (a scanned PDF needs OCR)")
    return text


def submission_text(conn, submission_id) -> tuple[str, str]:
    """``(text, file type)`` of an assignment submission: its stored text,
    else read from its file."""
    row = conn.execute("SELECT content, file_path FROM assignment_submissions WHERE id = ?",
                       (submission_id,)).fetchone()
    if not row:
        raise ValueError(f"No submission {submission_id}")
    if row[0] and str(row[0]).strip():
        return str(row[0]), "txt"
    if not row[1]:
        raise ValueError("This submission has no text or file to read")
    return extract(row[1]), file_type(row[1])
