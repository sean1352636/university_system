"""The branded look of outgoing e-mail.

Almost every message in the system is written as plain text: templates,
f-strings, reports, digests. ``render`` turns that text into an HTML e-mail
in the institution's colours (Branding & Customization) and ``smtp.build_message``
sends it beside the original text, so nothing is lost for a client that
shows plain text only.

The text is read, not trusted: every character is escaped. Structure that
the text already has is kept and shown properly:

* a line underlined with ``===`` or ``---`` is a heading;
* a run of ``•``/``-``/``*`` or ``1.`` lines is a list;
* a run of ``Label: value`` lines is a details table;
* aligned columns (reports, box drawing) stay in a fixed-width block;
* the closing ("Best regards, …") is set as a signature;
* web and e-mail addresses become links.

Turned off with the ``html_layout`` e-mail setting (Delivery → Settings).
"""

from __future__ import annotations

import html
import logging
import re
import time

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_BRAND", "LOGO_CID", "branding", "enabled", "logo", "render",
           "wrap_fragment", "email_html",
           "text_to_html"]

DEFAULT_BRAND = {
    "name": "the University",
    "tagline": "",
    "primary": "#2C3E50",
    "secondary": "#3498DB",
    "accent": "#E74C3C",
    "footer": "",
}

_BRAND_KEYS = {
    "branding_institution_name": "name",
    "branding_tagline": "tagline",
    "branding_primary_color": "primary",
    "branding_secondary_color": "secondary",
    "branding_accent_color": "accent",
    "branding_footer_text": "footer",
}
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}){1,2}$")
_CACHE_SECONDS = 60
_cache: dict = {}

FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, "
        "sans-serif")
MONO = "SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"
TEXT = "#1f2933"
MUTED = "#616e7c"
RULE = "#e4e7eb"
PAGE = "#f4f6f8"


# ── settings ────────────────────────────────────────────────────────────


def _connect():
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(row_factory=False)


def _cached(key, load):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    value = load()
    _cache[key] = (time.monotonic(), value)
    return value


def _load_branding() -> dict:
    brand = dict(DEFAULT_BRAND)
    try:
        from education_system.systems.university.infrastructure.email.sign_off import (
            institution_name,
        )
        brand["name"] = institution_name()
        conn = _connect()
        try:
            marks = ",".join("?" * len(_BRAND_KEYS))
            rows = conn.execute(
                f"SELECT setting_name, setting_value FROM security_settings "  # nosec B608
                f"WHERE setting_name IN ({marks})", list(_BRAND_KEYS)).fetchall()
        finally:
            conn.close()
        for name, value in rows:
            if value and str(value).strip() and name != "branding_institution_name":
                brand[_BRAND_KEYS[name]] = str(value).strip()
    except Exception:  # no table, no database yet: the defaults still look right
        logger.debug("Branding not read; using the default e-mail colours", exc_info=True)
    return _clean(brand)


def _clean(brand: dict) -> dict:
    """Only colours that are colours reach the markup."""
    out = dict(DEFAULT_BRAND)
    out.update({k: v for k, v in (brand or {}).items() if v})
    for key in ("primary", "secondary", "accent"):
        if not _HEX.match(str(out[key])):
            out[key] = DEFAULT_BRAND[key]
    return out


def branding() -> dict:
    """Institution name, tagline, colours and footer, refreshed every minute."""
    return _cached("brand", _load_branding)


# ── logo ────────────────────────────────────────────────────────────────

LOGO_CID = "institution-logo"
LOGO_HEIGHT = 48          # shown in the header at this height (CSS pixels)
_LOGO_SCALE = 2           # stored at twice that, for sharp high-density screens
_LOGO_MAX_WIDTH = 220     # a wide wordmark is limited by width instead
_LOGO_MAX_BYTES = 300_000
_LOGO_TYPES = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif"}


def _logo_file():
    """The logo Branding & Customization points at; when no path is saved,
    the ``logo.*`` its Browse button stores in the branding folder."""
    from education_system.paths import UNIVERSITY_BRANDING_DIR
    from pathlib import Path
    raw = ""
    try:
        conn = _connect()
        try:
            row = conn.execute("SELECT setting_value FROM security_settings "
                               "WHERE setting_name = 'branding_logo_path'").fetchone()
        finally:
            conn.close()
        raw = (row[0] or "").strip() if row else ""
    except Exception:
        logger.debug("Logo setting not read", exc_info=True)
    if raw:
        path = Path(raw)
        path = path if path.is_absolute() else UNIVERSITY_BRANDING_DIR / path
        return path if path.is_file() else None
    for suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        candidate = UNIVERSITY_BRANDING_DIR / f"logo{suffix}"
        if candidate.is_file():
            return candidate
    return None


def load_logo(path) -> dict | None:
    """``{"data", "subtype", "width", "height"}`` ready to embed, or ``None``.
    Width and height are the display size; the image itself is twice that."""
    from pathlib import Path
    path = Path(path)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        import io
        with Image.open(path) as im:
            im.load()
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
            target_h = LOGO_HEIGHT * _LOGO_SCALE
            width = max(1, round(im.width * target_h / im.height))
            if width > _LOGO_MAX_WIDTH * _LOGO_SCALE:
                width = _LOGO_MAX_WIDTH * _LOGO_SCALE
                target_h = max(1, round(im.height * width / im.width))
            im = im.resize((width, target_h), Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, "PNG", optimize=True)
        return {"data": out.getvalue(), "subtype": "png",
                "width": max(1, round(width / _LOGO_SCALE)),
                "height": max(1, round(target_h / _LOGO_SCALE))}
    # Without Pillow: a small PNG/JPEG/GIF is sent as it is, shown 48px high.
    subtype = _LOGO_TYPES.get(path.suffix.lower())
    if not subtype or path.stat().st_size > _LOGO_MAX_BYTES:
        return None
    return {"data": path.read_bytes(), "subtype": subtype, "width": None,
            "height": LOGO_HEIGHT}


def _load_logo() -> dict | None:
    try:
        path = _logo_file()
        return load_logo(path) if path else None
    except Exception:  # an unreadable image must never stop an e-mail
        logger.warning("Branding logo not usable in e-mail", exc_info=True)
        return None


def logo() -> dict | None:
    """The institution logo for the e-mail header, refreshed every minute."""
    return _cached("logo", _load_logo)


def _load_enabled() -> bool:
    try:
        conn = _connect()
        try:
            row = conn.execute("SELECT value FROM email_settings WHERE key = 'html_layout'"
                               ).fetchone()
        finally:
            conn.close()
        return not row or str(row[0]).strip() != "0"
    except Exception:
        return True


def enabled() -> bool:
    """Whether plain-text e-mail is sent with the branded HTML version."""
    return _cached("enabled", _load_enabled)


def clear_cache() -> None:
    _cache.clear()


# ── text to HTML ────────────────────────────────────────────────────────

_URL = re.compile(r"(https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]])")
_EMAIL = re.compile(r"(?<![\w.+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_UNDERLINE = re.compile(r"^\s*([=\-~_━─═—*])\1{2,}\s*$")
_BULLET = re.compile(r"^\s*(?:[•●▪◦‣–\-*]|•)\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d{1,3})[.)]\s+(.*)$")
_PAIR = re.compile(r"^\s*([^:\n]{1,40}?)\s*:\s+(\S.*)$")
_PAIR_EMPTY = re.compile(r"^\s*([^:\n]{1,40}?):\s*$")
_COLUMNS = re.compile(r"\S {3,}\S|[│┃║┌┐└┘├┤┬┴┼─━═|+]{2,}|\t")
_CLOSINGS = re.compile(
    r"^(best regards|kind regards|warm regards|regards|best wishes|many thanks|thanks|"
    r"thank you|yours sincerely|yours faithfully|sincerely|cheers|with thanks)\b[,.!]?\s*$",
    re.I)


def _inline(text: str, link: str) -> str:
    """Escape one run of text and turn addresses into links."""
    out, last = [], 0
    for match in sorted(list(_URL.finditer(text)) + list(_EMAIL.finditer(text)),
                        key=lambda m: m.start()):
        if match.start() < last:
            continue
        out.append(html.escape(text[last:match.start()]))
        found = match.group(1)
        href = found if found.lower().startswith("http") else f"mailto:{found}"
        out.append(f'<a href="{html.escape(href, quote=True)}" '
                   f'style="color:{link};text-decoration:underline;">{html.escape(found)}</a>')
        last = match.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def _paragraph(lines, link) -> str:
    body = "<br>".join(_inline(line.strip(), link) for line in lines)
    return (f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:{TEXT};">'
            f"{body}</p>")


def _heading(text, level, brand) -> str:
    size, colour = ("19px", brand["primary"]) if level == 2 else ("16px", TEXT)
    return (f'<h{level} style="margin:24px 0 10px;font-size:{size};line-height:1.3;'
            f'font-weight:600;color:{colour};">{_inline(text.strip().rstrip(":"), brand["secondary"])}'
            f"</h{level}>")


def _list(items, ordered, link) -> str:
    tag = "ol" if ordered else "ul"
    rows = "".join(f'<li style="margin:0 0 6px;">{_inline(i, link)}</li>' for i in items)
    return (f'<{tag} style="margin:0 0 16px;padding-left:22px;font-size:15px;'
            f'line-height:1.6;color:{TEXT};">{rows}</{tag}>')


def _details(pairs, brand) -> str:
    rows = []
    for n, (label, value) in enumerate(pairs):
        top = "" if n == 0 else f"border-top:1px solid {RULE};"
        rows.append(
            f'<tr><td style="padding:9px 14px;{top}font-size:13px;color:{MUTED};'
            f'width:38%;vertical-align:top;">{_inline(label, brand["secondary"])}</td>'
            f'<td style="padding:9px 14px;{top}font-size:14px;color:{TEXT};'
            f'font-weight:600;vertical-align:top;">{_inline(value, brand["secondary"])}</td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 18px;border:1px solid {RULE};border-left:4px solid '
            f'{brand["secondary"]};border-radius:6px;border-collapse:separate;'
            f'background:#f9fafb;">{"".join(rows)}</table>')


def _pre(lines) -> str:
    text = html.escape("\n".join(line.rstrip() for line in lines))
    return (f'<pre style="margin:0 0 16px;max-width:100%;padding:14px;background:#f7f8fa;border:1px solid '
            f'{RULE};border-radius:6px;font-family:{MONO};font-size:12.5px;line-height:1.5;'
            f'color:{TEXT};white-space:pre;overflow-x:auto;">{text}</pre>')


_CELL_GAP = re.compile(r"\s{2,}|\t")
_NUMBERISH = re.compile(r"^[-+]?[£$€]?\d[\d,.]*%?$")


def _cells(line) -> list[str]:
    return [c for c in _CELL_GAP.split(line.strip()) if c]


def _grid(lines) -> tuple[list[str], list[str], list[list[str]]] | None:
    """``(title lines, header, rows)`` when the lines are a column report
    whose every row can be read into the header's columns, else ``None``.
    A row whose first column ran into the second ("School of Law 3") is
    split at its last word when that word is a number."""
    start = next((n for n, line in enumerate(lines) if len(_cells(line)) >= 3), None)
    if start is None or start > 2 or len(lines) - start < 2:
        return None
    header, first = _cells(lines[start]), start + 1
    above = lines[start - 1].split() if start else []
    if len(above) == len(header) and len(_cells(lines[start - 1])) < 3:
        # "Code Name Credits" written with single spaces over real columns.
        header, first, start = above, start, start - 1
    rows = _rows(header, lines[first:])
    return None if rows is None else (lines[:start], header, rows)


def _rows(header, lines) -> list[list[str]] | None:
    rows = []
    for n, line in enumerate(lines):
        if n == len(lines) - 1 and n and line.strip()[:1] in "…(.":
            rows.append([line.strip()])  # "… (344 more lines)" closes the table
            break
        cells = _cells(line)
        if len(cells) == len(header) - 1 and " " in cells[0]:
            first, last = cells[0].rsplit(" ", 1)
            if _NUMBERISH.match(last):
                cells = [first, last, *cells[1:]]
        if len(cells) != len(header):
            return None
        rows.append(cells)
    return rows or None


def _table(header, rows, brand) -> str:
    full = [row for row in rows if len(row) == len(header)]
    numeric = {n for n in range(1, len(header))
               if full and all(_NUMBERISH.match(row[n]) for row in full)}

    def cell(value, tag, n, top):
        align = "right" if n in numeric else "left"
        weight = "600" if tag == "th" else "400"
        colour = MUTED if tag == "th" else TEXT
        return (f'<{tag} style="padding:7px 10px;{top}text-align:{align};font-size:13px;'
                f'font-weight:{weight};color:{colour};">{html.escape(value)}</{tag}>')
    head = "".join(cell(v, "th", n, f"border-bottom:2px solid {RULE};")
                   for n, v in enumerate(header))
    def line(row):
        if len(row) == 1 and len(header) > 1:  # the closing note spans the table
            return (f'<tr><td colspan="{len(header)}" style="padding:7px 10px;border-top:1px '
                    f'solid {RULE};font-size:13px;color:{MUTED};">{html.escape(row[0])}</td></tr>')
        return "<tr>" + "".join(cell(v, "td", n, f"border-top:1px solid {RULE};")
                                for n, v in enumerate(row)) + "</tr>"
    body = "".join(line(row) for row in rows)
    return ('<div style="overflow-x:auto;margin:0 0 18px;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;">'
            f"<tr>{head}</tr>{body}</table></div>")


def _signature(lines, brand) -> str:
    first, rest = lines[0].strip(), [line.strip() for line in lines[1:] if line.strip()]
    body = _inline(first, brand["secondary"])
    if rest:
        body += "<br>" + "<br>".join(
            f'<strong style="color:{TEXT};">{_inline(line, brand["secondary"])}</strong>'
            if n == 0 else _inline(line, brand["secondary"]) for n, line in enumerate(rest))
    return (f'<p style="margin:24px 0 0;padding-top:16px;border-top:1px solid {RULE};'
            f'font-size:14px;line-height:1.6;color:{MUTED};">{body}</p>')


def _blocks(text: str) -> list[list[str]]:
    blocks, current = [], []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _ruled_table(lines, cut, brand, out) -> bool:
    """"Name    Count" over "-----" over rows: the rule underlines a table
    header. Renders it and returns True, or returns False and renders nothing."""
    end = next((n for n in range(cut + 1, len(lines)) if _UNDERLINE.match(lines[n])),
               len(lines))
    body = lines[cut + 1:end]
    for header in (_cells(lines[cut - 1]), lines[cut - 1].split()):
        rows = _rows(header, body) if len(header) >= 2 and body else None
        if rows and any(len(row) > 1 for row in rows):
            _render_block(lines[:cut - 1], brand, out)
            out.append(_table(header, rows, brand))
            _render_block(lines[end + 1:], brand, out)
            return True
    return False


def _render_block(lines, brand, out) -> None:
    link = brand["secondary"]
    # Headings: "Title" over "=====" (or a lone rule, which is a divider).
    while lines and _UNDERLINE.match(lines[0]):
        out.append(f'<hr style="border:0;border-top:1px solid {RULE};margin:20px 0;">')
        lines = lines[1:]
    if len(lines) >= 3 and _UNDERLINE.match(lines[1]) and _ruled_table(lines, 1, brand, out):
        return
    if len(lines) >= 2 and _UNDERLINE.match(lines[1]):
        level = 2 if lines[1].strip()[0] in "=═━" else 3
        out.append(_heading(lines[0], level, brand))
        lines = lines[2:]
        if lines:
            _render_block(lines, brand, out)
        return
    if not lines:
        return
    # A rule inside the block ("━━━━" around a set of details) separates
    # what is above it from what is below.
    cut = next((n for n, line in enumerate(lines) if _UNDERLINE.match(line)), None)
    if cut and _ruled_table(lines, cut, brand, out):
        return
    if cut is not None:
        _render_block(lines[:cut], brand, out)
        _render_block(lines[cut + 1:], brand, out)
        return

    if len(lines) == 1 and _PAIR_EMPTY.match(lines[0]) and len(lines[0].strip()) <= 60:
        out.append(_heading(lines[0], 3, brand))
        return

    bullets = [_BULLET.match(line) for line in lines]
    if all(bullets):
        out.append(_list([m.group(1) for m in bullets], False, link))
        return
    numbers = [_NUMBERED.match(line) for line in lines]
    if len(lines) > 1 and all(numbers):
        out.append(_list([m.group(2) for m in numbers], True, link))
        return

    pairs = [_PAIR.match(line) for line in lines]
    if len(lines) > 1 and all(pairs) and not any("://" in m.group(1) for m in pairs):
        out.append(_details([(m.group(1).strip(), m.group(2).strip()) for m in pairs], brand))
        return
    # "Heading:" then a list or details under it.
    if len(lines) > 1 and _PAIR_EMPTY.match(lines[0]):
        out.append(_heading(lines[0].strip().rstrip(":"), 3, brand))
        _render_block(lines[1:], brand, out)
        return
    # A lead-in line, then a list ("You have 3 things due:" / "• …").
    if len(lines) > 1 and not bullets[0] and all(bullets[1:]):
        out.append(_paragraph(lines[:1], link))
        out.append(_list([m.group(1) for m in bullets[1:]], False, link))
        return

    if sum(1 for line in lines if _COLUMNS.search(line.strip())) >= max(2, len(lines) // 2):
        grid = _grid(lines)
        if grid:
            title, header, rows = grid
            for line in title:
                out.append(_heading(line, 3, brand))
            out.append(_table(header, rows, brand))
        else:
            out.append(_pre(lines))
        return
    out.append(_paragraph(lines, link))


def text_to_html(text: str, brand: dict | None = None) -> str:
    """The body of the e-mail, as HTML, from plain text."""
    brand = _clean(brand or DEFAULT_BRAND)
    blocks = _blocks(text or "")
    closing = None
    if blocks and _CLOSINGS.match(blocks[-1][0].strip()) and len(blocks[-1]) <= 6:
        closing = blocks.pop()
    out: list[str] = []
    for lines in blocks:
        _render_block(lines, brand, out)
    if closing:
        out.append(_signature(closing, brand))
    return "\n".join(out)


# ── the page ────────────────────────────────────────────────────────────


def _preheader(text: str) -> str:
    first = next((line.strip() for line in (text or "").splitlines()
                  if line.strip() and not _UNDERLINE.match(line)), "")
    return html.escape(first[:140])


def _masthead(name: str, tagline: str, image: dict | None) -> str:
    words = (f'<div style="font-size:18px;font-weight:700;letter-spacing:.2px;color:#ffffff;'
             f'font-family:{FONT};">{name}</div>{tagline}')
    if not image or not image.get("src"):
        return words
    size = f'height="{image["height"]}"' + (f' width="{image["width"]}"' if image.get("width")
                                             else "")
    css = f'height:{image["height"]}px;' + (f'width:{image["width"]}px;' if image.get("width")
                                            else "width:auto;")
    return ('<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="padding-right:14px;vertical-align:middle;">'
            f'<img src="{html.escape(image["src"], quote=True)}" {size} alt="{name}" '
            f'style="display:block;border:0;outline:none;{css}"></td>'
            f'<td style="vertical-align:middle;">{words}</td></tr></table>')


def _page(subject: str, inner: str, preheader: str, brand: dict,
          image: dict | None = None) -> str:
    name = html.escape(brand["name"])
    tagline = (f'<div style="margin-top:4px;font-size:13px;color:#ffffff;opacity:.85;">'
               f'{html.escape(brand["tagline"])}</div>') if brand["tagline"] else ""
    footer = html.escape(brand["footer"]) if brand["footer"] else ""
    title = html.escape(subject or "")
    heading = (f'<h1 style="margin:0 0 20px;font-size:22px;line-height:1.3;font-weight:600;'
               f'color:{TEXT};">{title}</h1>') if title else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{PAGE};font-family:{FONT};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;table-layout:fixed;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid {RULE};">
<tr><td style="background:{brand['primary']};padding:{'16px' if image else '22px'} 32px;">
{_masthead(name, tagline, image)}
</td></tr>
<tr><td style="height:4px;line-height:4px;font-size:0;background:{brand['secondary']};">&nbsp;</td></tr>
<tr><td style="padding:30px 32px 32px;font-family:{FONT};">
{heading}{inner}
</td></tr>
<tr><td style="padding:18px 32px;background:#f9fafb;border-top:1px solid {RULE};font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};">
This e-mail was sent by {name}.{('<br>' + footer) if footer else ''}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def render(subject: str, text: str, brand: dict | None = None,
           image: dict | None = None) -> str:
    """A complete HTML e-mail for a plain-text message. ``image`` is the
    header logo: ``{"src", "width", "height"}``."""
    brand = _clean(brand if brand is not None else branding())
    return _page(subject, text_to_html(text, brand), _preheader(text), brand, image)


def wrap_fragment(subject: str, fragment: str, plain_text: str = "",
                  brand: dict | None = None, image: dict | None = None) -> str:
    """Put an HTML fragment (``<p>…</p>`` from a template) in the same frame.
    The fragment is already markup and is used as given."""
    brand = _clean(brand if brand is not None else branding())
    inner = (f'<div style="font-size:15px;line-height:1.6;color:{TEXT};">{fragment}</div>')
    return _page(subject, inner, _preheader(plain_text), brand, image)


def email_html(subject: str, body: str, fragment: bool = False,
               plain_text: str = "") -> tuple[str, dict | None]:
    """``(html, logo)`` for an outgoing message. When there is a logo, the
    page refers to it as ``cid:institution-logo`` and the caller attaches
    ``logo["data"]`` under that Content-ID."""
    picture = logo()
    image = dict(picture, src=f"cid:{LOGO_CID}") if picture else None
    if fragment:
        return wrap_fragment(subject, body, plain_text, image=image), picture
    return render(subject, body, image=image), picture
