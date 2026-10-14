"""Shared presentation helpers for report-style GUI screens.

Reports across the academic GUIs were each rendering into a
``ScrolledText`` as pre-formatted, fixed-width text — fine to produce,
hard to read, impossible to sort, and it silently mangles any value
wider than the column padding assumed.

These helpers replace that with a small vocabulary: a banner header, a
strip of headline numbers, fill bars, and a real ``Treeview`` table.
Course Management grew them first; Library needs the same thing, so
they live here rather than being copied a third time.

Mix ``ReportPresentationMixin`` into a GUI class and call the methods on
``self`` — they only need a Tk parent widget, not any particular host.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


def _split_row(entry, known_tags):
    """Split a ``_report_table`` row into ``(values, tag)``.

    A row is a tagged pair only when it is a 2-sequence whose second element
    is a tag the caller declared (or None). Anything else is data — including
    a 2-column tuple of values, which the old ``isinstance(entry, tuple)``
    test would have torn in half.
    """
    if isinstance(entry, (list, tuple)) and len(entry) == 2:
        values, maybe_tag = entry
        if isinstance(values, (list, tuple)) and (
                maybe_tag is None or maybe_tag in known_tags):
            return values, maybe_tag
    return entry, None


class ReportPresentationMixin:
    """Card, table and headline-number builders for report screens."""

    # --- Flat-UI palette, shared by every report surface ---
    DETAIL_BG = "#eef1f4"      # page background behind the cards
    _C_HEADER = "#2c3e50"      # dark header banner
    _C_CARD = "#ffffff"        # card surface
    _C_ACCENT = "#3498db"      # section accent / stat numbers
    _C_LABEL = "#6b7280"       # muted field labels
    _C_VALUE = "#1f2933"       # field values
    _C_MUTED = "#95a5a6"       # timestamps / secondary text
    _DETAIL_FONT = "Segoe UI"  # Tk substitutes a sane default where absent

    def _scrollable_area(self, parent, bg=None):
        """Return (inner_frame) hosted on a scrollable canvas inside ``parent``.

        The inner frame stretches to the canvas width and scrolls with the
        wheel while the pointer is over it. Used by both the course-details
        tab and the analytics report windows.
        """
        bg = bg or self.DETAIL_BG
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, bg=bg)
        vbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _wheel(event):
            delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: (
            canvas.bind_all("<MouseWheel>", _wheel),
            canvas.bind_all("<Button-4>", _wheel),
            canvas.bind_all("<Button-5>", _wheel),
        ))
        canvas.bind("<Leave>", lambda e: (
            canvas.unbind_all("<MouseWheel>"),
            canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>"),
        ))
        return inner
    def _report_header(self, parent, title, subtitle=None):
        """Dark banner used at the top of the analytics report windows."""
        header = tk.Frame(parent, bg=self._C_HEADER)
        header.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(
            header, text=title, font=(self._DETAIL_FONT, 16, "bold"),
            bg=self._C_HEADER, fg="white", anchor="w",
        ).pack(anchor="w", padx=18, pady=(14, 0 if subtitle else 14))
        if subtitle:
            tk.Label(
                header, text=subtitle, font=(self._DETAIL_FONT, 10),
                bg=self._C_HEADER, fg="#bdc3c7", anchor="w",
            ).pack(anchor="w", padx=18, pady=(2, 12))
    def _stat_strip(self, parent, items, accent=None):
        """Row of headline number cards. ``items`` is a list of (value, label)."""
        accent = accent or self._C_ACCENT
        strip = tk.Frame(parent, bg=self.DETAIL_BG)
        strip.pack(fill=tk.X, padx=2, pady=(2, 0))
        for c in range(len(items)):
            strip.columnconfigure(c, weight=1, uniform="stat")
        for c, (num, lab) in enumerate(items):
            cell = tk.Frame(strip, bg=self._C_CARD, highlightbackground="#e5e7eb", highlightthickness=1)
            cell.grid(row=0, column=c, sticky="ew", padx=4, pady=6)
            tk.Label(cell, text=str(num), font=(self._DETAIL_FONT, 16, "bold"),
                     bg=self._C_CARD, fg=accent).pack(pady=(10, 0))
            tk.Label(cell, text=lab, font=(self._DETAIL_FONT, 9),
                     bg=self._C_CARD, fg=self._C_LABEL).pack(pady=(0, 10))
        return strip
    def _fill_bar(self, parent, percent, label=None):
        """A labelled horizontal fill-rate bar, colour-coded by utilisation."""
        pct = max(0.0, min(100.0, percent))
        colour = "#2ecc71" if pct < 75 else "#f39c12" if pct < 95 else "#e74c3c"
        wrap = tk.Frame(parent, bg=self._C_CARD)
        wrap.pack(fill=tk.X, pady=4)
        if label:
            tk.Label(wrap, text=label, font=(self._DETAIL_FONT, 9),
                     bg=self._C_CARD, fg=self._C_LABEL).pack(anchor="w")
        track = tk.Frame(wrap, bg="#e5e7eb", height=18)
        track.pack(fill=tk.X, pady=(2, 0))
        track.pack_propagate(False)
        fill = tk.Frame(track, bg=colour)
        fill.place(relwidth=pct / 100.0, relheight=1.0)
        tk.Label(track, text=f"{pct:.1f}%", font=(self._DETAIL_FONT, 8, "bold"),
                 bg="#e5e7eb", fg=self._C_HEADER).place(relx=1.0, x=-4, rely=0.5, anchor="e")
        return wrap
    def _text_card(self, parent, lines):
        """A white card of wrapped prose — for report text that isn't tabular."""
        card = tk.Frame(parent, bg=self._C_CARD,
                        highlightbackground="#e5e7eb", highlightthickness=1)
        card.pack(fill=tk.X, padx=6, pady=4)
        label = tk.Label(card, text="\n".join(lines), font=(self._DETAIL_FONT, 10),
                         bg=self._C_CARD, fg=self._C_VALUE, anchor="w",
                         justify="left", wraplength=760)
        label.pack(fill=tk.X, padx=12, pady=10)
        card.bind("<Configure>", lambda e, l=label: l.configure(
            wraplength=max(240, e.width - 28)))
        return card

    def _ensure_report_tree_style(self):
        """Configure a tidy Treeview style for report tables (idempotent)."""
        if getattr(self, "_report_tree_styled", False):
            return
        style = ttk.Style()
        style.configure("Report.Treeview", rowheight=26, font=(self._DETAIL_FONT, 10),
                        background=self._C_CARD, fieldbackground=self._C_CARD)
        style.configure("Report.Treeview.Heading", font=(self._DETAIL_FONT, 10, "bold"))
        self._report_tree_styled = True
    def _report_table(self, parent, columns, rows, widths=None, anchors=None,
                      tag_colours=None, height=12):
        """Build a styled Treeview table inside a card and return it.

        ``columns`` -> list of headings.

        ``rows`` -> either plain value sequences, or ``(values, tag)`` pairs
        where *tag* names an entry in ``tag_colours``. The two forms may be
        mixed, and a row may be a list or a tuple: a bare 7-column tuple used
        to be mistaken for a tagged pair and blow up with "too many values to
        unpack", which made passing a tuple of data a silent trap.

        ``tag_colours`` -> {tag: foreground}. Zebra striping is applied on top.
        """
        self._ensure_report_tree_style()
        card = tk.Frame(parent, bg=self._C_CARD, highlightbackground="#e5e7eb", highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        holder = tk.Frame(card, bg=self._C_CARD)
        holder.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tree = ttk.Treeview(holder, columns=columns, show="headings",
                            style="Report.Treeview", height=min(height, max(3, len(rows))))
        widths = widths or {}
        anchors = anchors or {}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 120), anchor=anchors.get(col, tk.W),
                        stretch=True)
        tree.tag_configure("_odd", background="#f7f9fb")
        tree.tag_configure("_even", background=self._C_CARD)
        for colour_tag, fg in (tag_colours or {}).items():
            tree.tag_configure(colour_tag, foreground=fg)
        known_tags = set(tag_colours or ())
        for i, entry in enumerate(rows):
            values, extra_tag = _split_row(entry, known_tags)
            tags = ["_odd" if i % 2 else "_even"]
            if extra_tag:
                tags.append(extra_tag)
            tree.insert("", tk.END, values=values, tags=tags)

        vsb = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        return tree


# --------------------------------------------------------------------------
# Turning the existing fixed-width text reports into structured blocks.
#
# Every report generator in the library GUI builds the same shape of
# string: a title, rule lines of ``=`` or ``-``, ALL-CAPS section
# headings ending in a colon, and then either ``Label: value`` pairs or
# whitespace-aligned table rows. Parsing that shape lets all of them be
# rendered as cards and tables without rewriting each generator, and
# keeps the original text intact for the email and save-to-file actions.
# --------------------------------------------------------------------------

# Rules are drawn with ASCII dashes in some reports and box-drawing characters
# in others (``═``, ``─``, ``━``). Matching only the ASCII set left a unicode
# rule to be parsed as content — which made the first one the report's "title".
_RULE = re.compile(r"^[=\-_*\u2500-\u257f\u2014\u2013]{3,}$")
_HEADING = re.compile(r"^([A-Z0-9][A-Z0-9 &/()'\-\.]{2,}):\s*$")
# A heading is also an ALL-CAPS line sitting against a rule, colon or not.
_BARE_HEADING = re.compile(r"^([A-Z0-9][A-Z0-9 &/()'\-\.,]{2,})$")
_KEYVALUE = re.compile(r"^\s*([^:]{1,60}?):\s{0,}(.*\S)\s*$")
_NUMERIC = re.compile(r"^[£$€]?-?[\d,]+(\.\d+)?%?$")


def _looks_numeric(value):
    return bool(_NUMERIC.match((value or "").strip()))


def _merge_currency(cells):
    """Rejoin a currency symbol split off its amount.

    Reports pad amounts as ``£    318.20`` to align a column, and the
    2+ space column split then leaves ``£`` stranded as its own cell,
    shifting every later column one to the right.
    """
    out = []
    for cell in cells:
        if out and out[-1] in ("£", "$", "€", "-£", "-$", "-€"):
            out[-1] = out[-1] + cell
        else:
            out.append(cell)
    return out


_LOWER_WORDS = {"BY", "OF", "AND", "THE", "TO", "IN", "FOR", "ON", "PER"}


def _titleise(heading):
    """Title-case a heading while leaving acronyms alone: ``GPA`` not ``Gpa``."""
    words = []
    for word in heading.split():
        if word.isupper() and len(word) <= 4 and word not in _LOWER_WORDS:
            words.append(word)
        else:
            words.append(word.title())
    return " ".join(words)


def parse_text_report(text):
    """Parse a fixed-width text report into ``(title, sections)``.

    ``sections`` is a list of ``{"heading", "pairs", "rows"}`` where
    *pairs* are ``(label, value)`` tuples and *rows* are the whitespace
    separated columns of anything that isn't a pair. A section carries
    whichever of the two it actually had; both may be empty, in which
    case the caller should fall back to showing the raw text.
    """
    lines = (text or "").splitlines()
    title, sections = "", []
    current = None

    def _flush():
        if current and (current["pairs"] or current["rows"]):
            sections.append(current)

    def _is_rule(index):
        return 0 <= index < len(lines) and bool(_RULE.match(lines[index].strip()))

    for i, raw in enumerate(lines):
        line = raw.rstrip()
        if not line.strip() or _RULE.match(line.strip()):
            continue

        heading = _HEADING.match(line.strip())
        banner = False
        if not heading and (_is_rule(i - 1) or _is_rule(i + 1)):
            # "PROGRESS BY CATEGORY" between two rules is a heading even
            # though it carries no colon.
            heading = _BARE_HEADING.match(line.strip())
            banner = bool(heading)
        if heading:
            if banner and not title and current is None:
                # A rule-flanked line at the very top is the report's banner
                # title, not its first section.
                title = _titleise(heading.group(1))
                continue
            _flush()
            current = {"heading": _titleise(heading.group(1)), "pairs": [], "rows": []}
            continue

        if not title and current is None:
            # The first non-rule line is the report's own title.
            title = line.strip()
            continue

        if current is None:
            current = {"heading": "", "pairs": [], "rows": []}

        pair = _KEYVALUE.match(line)
        if pair and not re.search(r"\s{2,}", pair.group(1).strip()):
            current["pairs"].append((pair.group(1).strip(), pair.group(2).strip()))
        else:
            cells = _merge_currency(
                [c for c in re.split(r"\s{2,}", line.strip()) if c])
            if len(cells) > 1:
                current["rows"].append(cells)
            elif cells:
                current["pairs"].append((cells[0], ""))

    _flush()
    return title, sections


def _group_pairs(pairs):
    """Split ``(label, value)`` pairs into consecutive prose / tabular runs.

    Yields ``(is_prose, group)``; a pair whose value is empty is prose.
    """
    groups = []
    for label, value in pairs:
        is_prose = not (value or "").strip()
        if groups and groups[-1][0] == is_prose:
            groups[-1][1].append((label, value))
        else:
            groups.append((is_prose, [(label, value)]))
    return groups


class TextReportRendererMixin(ReportPresentationMixin):
    """Renders a parsed fixed-width text report as cards and tables."""

    def render_text_report(self, parent, text, title=None, subtitle=None):
        """Draw *text* into *parent* as a banner, stat strip and tables.

        Returns True if anything structured was rendered. When the text
        doesn't parse into sections the caller should fall back to
        showing it verbatim — an unrecognised report must still be
        readable rather than silently blank.
        """
        parsed_title, sections = parse_text_report(text)
        if not sections:
            return False

        inner = self._scrollable_area(parent)
        self._report_header(inner, title or parsed_title or "Report", subtitle)

        # A leading unheaded section holds the report's own metadata
        # (Generated, Period, ...) — show it under the banner, not as a card.
        if sections and not sections[0]["heading"] and sections[0]["pairs"]:
            meta = "   ".join(f"{k}: {v}" for k, v in sections[0]["pairs"])
            tk.Label(inner, text=meta, font=(self._DETAIL_FONT, 9),
                     bg=self.DETAIL_BG, fg=self._C_MUTED, anchor="w",
                     ).pack(fill=tk.X, padx=10, pady=(6, 0))
            sections = sections[1:]

        first_numeric = True
        for sec in sections:
            pairs, rows = sec["pairs"], sec["rows"]

            # An all-numeric block of pairs reads best as headline figures,
            # but only the first one — a page of stat strips is worse than
            # a table, so later numeric blocks become two-column tables.
            if pairs and not rows and first_numeric and \
                    all(_looks_numeric(v) for _, v in pairs) and len(pairs) <= 6:
                self._section_label(inner, sec["heading"])
                self._stat_strip(inner, [(v, k) for k, v in pairs])
                first_numeric = False
                continue

            if pairs:
                self._section_label(inner, sec["heading"])
                # A "pair" with no value is really a line of prose — a warning
                # message, a recommendation, a note. Squeezing those into a
                # 320px Item column truncated them; they get a text card
                # instead, and consecutive runs keep the report's own order.
                for is_prose, group in _group_pairs(pairs):
                    if is_prose:
                        self._text_card(inner, [k for k, _ in group])
                    else:
                        self._report_table(
                            inner, ["Item", "Value"], [(k, v) for k, v in group],
                            widths={"Item": 320, "Value": 160},
                            anchors={"Value": tk.E}, height=min(14, len(group)))

            if rows:
                self._section_label(inner, sec["heading"] if not pairs else "")
                width = max(len(r) for r in rows)
                header, body = self._table_header(rows, width)
                self._report_table(
                    inner, header, body,
                    anchors={c: tk.E for c in header[1:]},
                    height=min(16, len(body)))
        return True

    @staticmethod
    def _table_header(rows, width):
        """Split a parsed table into (column names, data rows).

        The first row is the header only when it is non-numeric and has
        the full column count; otherwise the table had no header line
        and inventing one from data would lose a row.
        """
        rows = [list(r) + [""] * (width - len(r)) for r in rows]
        first = rows[0]
        if len(rows) > 1 and not any(_looks_numeric(c) for c in first if c):
            return [c or f"Column {i+1}" for i, c in enumerate(first)], rows[1:]
        return [f"Column {i+1}" for i in range(width)], rows

    def _section_label(self, parent, text):
        if not text:
            return
        tk.Label(parent, text=text, font=(self._DETAIL_FONT, 11, "bold"),
                 bg=self.DETAIL_BG, fg=self._C_HEADER, anchor="w",
                 ).pack(fill=tk.X, padx=10, pady=(12, 2))


# --------------------------------------------------------------------------
# Section-based reports
#
# Grade Tracking builds its reports as ``[(heading, [line, ...]), ...]``
# and dumped the lot into a Courier ScrolledText in an 800x600 window.
# The structure is already there, so it can be rendered directly rather
# than parsed back out of formatted text.
# --------------------------------------------------------------------------

_PIPE_FIELD = re.compile(r"\s*\|\s*")


def _split_section_lines(lines):
    """Work out the best shape for one section's lines.

    Returns ``(kind, payload)`` where kind is "table", "pairs" or "text".
    Lines are only treated as a table when *every* line agrees on the
    column count — a single odd line means the section is prose, and
    forcing it into columns would shred it.
    """
    cleaned = [l for l in (lines or []) if str(l).strip()]
    if not cleaned:
        return "text", []

    # Pipe-separated fields: "Name (id): GPA: 3.2 | Projected: 3.4"
    piped = [_PIPE_FIELD.split(str(l).strip()) for l in cleaned]
    widths = {len(p) for p in piped}
    if len(widths) == 1 and widths.pop() > 1:
        return "table", piped

    # "Label: value" throughout
    pairs = []
    for line in cleaned:
        text = str(line).strip()
        if ":" in text:
            label, _, value = text.partition(":")
            if label.strip() and len(label) <= 60:
                pairs.append((label.strip(), value.strip()))
                continue
        pairs = []
        break
    if pairs:
        return "pairs", pairs

    return "text", [str(l) for l in cleaned]


#: "Alice Smith (S123): Current GPA: 3.20" -> subject / label / value.
#: The subject is optional and only the first cell of a row normally has
#: one, which is what identifies the row.
_LABELLED_CELL = re.compile(
    r"^(?:(?P<subject>.*?):\s*)?(?P<label>[A-Za-z][\w /%()&.-]{0,40}):\s*(?P<value>.*)$")


def _parse_cell(cell):
    """(subject, label, value) for one cell; label/value None if unlabelled."""
    match = _LABELLED_CELL.match(cell.strip())
    if not match:
        return cell.strip(), None, None
    return (match.group("subject") or "").strip(), match.group("label").strip(), \
        match.group("value").strip()


def _column_names(rows):
    """Header names and cell values for a pipe-split table.

    Cells usually read "Label: value", and when a column carries the same
    label on every row that label becomes the heading so the value can
    stand alone. The first cell often also carries the thing the row is
    about ("Alice Smith (S123): Current GPA: 3.20"); that subject is
    split into its own leading column rather than being crushed into the
    first value, which is what made these tables unreadable.
    """
    width = len(rows[0])
    parsed = [[_parse_cell(cell) for cell in row] for row in rows]

    # Does column 0 carry a per-row subject?
    subjects = [row[0][0] for row in parsed]
    has_subject = all(subjects) and len(set(subjects)) > 1

    headers, body = [], []
    if has_subject:
        headers.append("Item")
    for col in range(width):
        labels = {row[col][1] for row in parsed}
        headers.append(labels.pop() if len(labels) == 1 and all(labels | {1})
                       else f"Column {col + 1}")
    # Re-derive cleanly: a single shared label names the column.
    headers = (["Item"] if has_subject else [])
    for col in range(width):
        labels = {row[col][1] for row in parsed}
        only = labels.pop() if len(labels) == 1 else None
        headers.append(only if only else f"Column {col + 1}")

    for row in parsed:
        cells = []
        if has_subject:
            cells.append(row[0][0])
        for col in range(width):
            subject, label, value = row[col]
            if label is None:
                cells.append(subject)
            elif col == 0 and has_subject:
                cells.append(value)
            elif subject:
                # A subject on a later column would be lost otherwise.
                cells.append(f"{subject}: {value}" if value else subject)
            else:
                cells.append(value)
        body.append(cells)
    return headers, body


class SectionReportMixin(ReportPresentationMixin):
    """Renders ``[(heading, [lines])]`` reports as cards and tables."""

    def render_report_sections(self, parent, title, sections, footer=None,
                               subtitle=None):
        """Draw *sections* into *parent*. Returns the scrollable frame."""
        inner = self._scrollable_area(parent)
        self._report_header(inner, title, subtitle or
                            f"Generated {_dt.datetime.now():%d %B %Y, %H:%M}")

        for heading, lines in sections or []:
            heading = (heading or "").strip() or "Details"
            tk.Label(inner, text=heading, font=(self._DETAIL_FONT, 11, "bold"),
                     bg=self.DETAIL_BG, fg=self._C_HEADER, anchor="w",
                     ).pack(fill=tk.X, padx=10, pady=(12, 2))

            kind, payload = _split_section_lines(lines)
            if kind == "table":
                headers, body = _column_names(payload)
                self._report_table(inner, headers, body,
                                   height=min(16, len(body)))
            elif kind == "pairs":
                self._report_table(inner, ["Item", "Value"], payload,
                                   widths={"Item": 320, "Value": 200},
                                   anchors={"Value": tk.E},
                                   height=min(16, len(payload)))
            elif payload:
                card = tk.Frame(inner, bg=self._C_CARD,
                                highlightbackground="#e5e7eb", highlightthickness=1)
                card.pack(fill=tk.X, padx=6, pady=4)
                label = tk.Label(card, text="\n".join(payload),
                                 font=(self._DETAIL_FONT, 9), bg=self._C_CARD,
                                 fg=self._C_VALUE, anchor="w", justify="left",
                                 wraplength=760)
                label.pack(fill=tk.X, padx=10, pady=8)
                card.bind("<Configure>", lambda e, l=label: l.configure(
                    wraplength=max(240, e.width - 24)))
            else:
                tk.Label(inner, text="No data available.",
                         font=(self._DETAIL_FONT, 9, "italic"),
                         bg=self.DETAIL_BG, fg=self._C_MUTED, anchor="w",
                         ).pack(fill=tk.X, padx=14, pady=2)

        if footer:
            tk.Label(inner, text=footer, font=(self._DETAIL_FONT, 9),
                     bg=self.DETAIL_BG, fg=self._C_MUTED, anchor="w",
                     wraplength=760, justify="left",
                     ).pack(fill=tk.X, padx=10, pady=(14, 8))
        return inner

    @staticmethod
    def sections_to_text(title, sections, footer=None):
        """The plain-text form, for emailing and saving to file."""
        lines = [title, "=" * len(title),
                 f"Generated: {_dt.datetime.now():%Y-%m-%d %H:%M}", ""]
        for heading, content in sections or []:
            heading = (heading or "").strip() or "Details"
            lines += [heading, "-" * len(heading)]
            lines += list(content) if content else ["No data available."]
            lines.append("")
        if footer:
            lines.append(footer)
        return "\n".join(lines).rstrip() + "\n"


class ReportPane(ttk.Frame, TextReportRendererMixin):
    """A report surface that accepts ``ScrolledText`` calls and draws cards.

    Report screens build their output by ``insert()``-ing pre-formatted lines
    into a ``ScrolledText``. Rewriting every one of those generators to emit
    widgets would be a large change for a cosmetic win, so this pane accepts
    the same calls, buffers the text, and renders the finished report through
    ``render_text_report`` — a banner, headline numbers, and real tables.

    Anything the parser cannot make sense of still shows verbatim in a text
    widget, so an unrecognised report is never blank.
    """

    # Options that belong to a Text widget and mean nothing to a Frame.
    _TEXT_ONLY_OPTIONS = frozenset({
        "height", "width", "wrap", "state", "font", "bg", "background",
        "fg", "foreground", "relief", "borderwidth", "bd", "padx", "pady",
        "insertbackground", "selectbackground", "spacing1", "spacing3",
        "undo", "autoseparators", "tabs",
    })

    def __init__(self, parent, title=None, subtitle=None, **kwargs):
        frame_options = {k: v for k, v in kwargs.items()
                         if k not in self._TEXT_ONLY_OPTIONS}
        ttk.Frame.__init__(self, parent, **frame_options)
        self._report_title = title
        self._report_subtitle = subtitle
        self._buffer = []
        self._render_job = None
        # A pane whose tab is never opened would otherwise be a blank area;
        # draw the placeholder straight away.
        self._schedule_render()

    # -- the slice of the Text API that report screens actually use ---------

    def insert(self, index, text="", *tags):
        """Append text. The index and tags are accepted and ignored."""
        self._buffer.append(text)
        self._schedule_render()

    def delete(self, *args):
        """Clear the pane. Ranges are accepted and ignored — reports rebuild
        their whole contents, never a slice of it."""
        self._buffer.clear()
        self._schedule_render()

    def tag_config(self, *args, **kwargs):
        """No-op: styling now comes from the rendered widgets."""

    tag_configure = tag_config

    def get(self, *args):
        """The buffered text, for callers that save or email the report."""
        return "".join(self._buffer)

    def see(self, *args):
        """No-op: the rendered pane scrolls itself."""

    def configure(self, cnf=None, **kwargs):
        """Apply Frame options, discarding Text-only ones such as ``state``."""
        options = dict(cnf or {}, **kwargs)
        frame_options = {k: v for k, v in options.items()
                         if k not in self._TEXT_ONLY_OPTIONS}
        if frame_options or not options:
            return ttk.Frame.configure(self, **frame_options)
        return None

    config = configure

    # -- rendering ----------------------------------------------------------

    def _schedule_render(self):
        """Coalesce a run of ``insert`` calls into a single redraw."""
        if self._render_job is not None:
            return
        try:
            self._render_job = self.after_idle(self._render)
        except tk.TclError:
            self._render_job = None

    def _render(self):
        self._render_job = None
        try:
            if not self.winfo_exists():
                return
            for child in self.winfo_children():
                child.destroy()
        except tk.TclError:
            return

        text = self.get()
        if not text.strip():
            tk.Label(self, text="No data available.",
                     font=(self._DETAIL_FONT, 10, "italic"),
                     bg=self.DETAIL_BG, fg=self._C_MUTED, anchor="w",
                     ).pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
            return

        try:
            rendered = self.render_text_report(
                self, text, self._report_title, self._report_subtitle)
        except tk.TclError:
            return
        except Exception:  # a malformed report must not take the screen down
            logger.debug("Falling back to plain text for report pane",
                         exc_info=True)
            rendered = False

        if not rendered:
            self._render_plain(text)

    def _render_plain(self, text):
        """Verbatim fallback for a report the parser doesn't recognise."""
        from tkinter import scrolledtext as _scrolledtext

        widget = _scrolledtext.ScrolledText(
            self, wrap=tk.WORD, font=("Consolas", 10),
            bg=self._C_CARD, fg=self._C_VALUE, relief=tk.FLAT)
        widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        widget.insert("1.0", text)
        widget.configure(state="disabled")
