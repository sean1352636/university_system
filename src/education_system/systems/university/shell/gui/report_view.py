"""A styled report surface for the Batch Operations GUI.

Every report in this package used to be an f-string of ``====`` rules
and bullet characters dumped into a Courier ``tk.Text``. That is fine
for a log and poor for a report: nothing is scannable, a percentage
looks the same whether it is 4% or 94%, and the reader has to parse the
numbers themselves to find the one thing that is wrong.

This builds reports out of real widgets instead of formatted text —
stat tiles, proportional bars, coloured severity pills, banded tables.
Real widgets rather than ``Text`` tags because a tag's background only
spans the glyphs it covers, so section rules and tiles built that way
end up ragged; a ``Frame`` is exactly as wide as you tell it to be.

Usage::

    view = ReportView(parent)
    view.pack(fill=tk.BOTH, expand=True)
    view.title("Data Quality Report", "Generated 2026-09-07 14:02")
    view.section("Completeness")
    view.metric("Email addresses", "94.2%", 94.2)
    view.freeze()

**Tone is the whole point.** ``metric`` and ``kv`` take a
``direction`` so the colour means something: 95% success is green,
95% error rate is red. Getting that backwards is worse than no colour
at all, so the default is ``higher_better`` and every lower-is-better
call site has to say so.

Every builder call also appends to a plain-text transcript, so
:meth:`to_text` still returns something an export or an email body can
use. Do not remove it — the quality report is displayed here but its
content is also read by the admin-email path.
"""

import logging
import re
import tkinter as tk
from tkinter import ttk, font as tkfont

logger = logging.getLogger(__name__)


# ── Palette ─────────────────────────────────────────────────────────

PAGE_BG = '#F4F6F8'
CARD_BG = '#FFFFFF'
RULE = '#DDE3E8'
TRACK = '#EDF1F4'        # unfilled portion of a bar
TEXT = '#2C3E50'
TEXT_MUTED = '#7F8C8D'
ACCENT = '#2E86C1'
HEADER_BG = '#34495E'

GOOD = '#27AE60'
WARN = '#F39C12'
BAD = '#E74C3C'
INFO = '#2E86C1'
NEUTRAL = '#7F8C8D'

TONES = {
    'good': GOOD, 'warn': WARN, 'bad': BAD,
    'info': INFO, 'muted': NEUTRAL, 'accent': ACCENT,
}

#: Tone thresholds. ``higher_better`` for success/completeness style
#: metrics, ``lower_better`` for error/failure style ones.
_THRESHOLDS = {
    'higher_better': ((90, 'good'), (70, 'warn')),
    'lower_better': ((5, 'good'), (15, 'warn')),
}


def tone_for(pct, direction='higher_better'):
    """Pick a tone for a percentage, or None when there is no number."""
    if pct is None:
        return 'muted'
    try:
        value = float(pct)
    except (TypeError, ValueError):
        return 'muted'
    if direction == 'lower_better':
        for limit, tone in _THRESHOLDS['lower_better']:
            if value <= limit:
                return tone
        return 'bad'
    for limit, tone in _THRESHOLDS['higher_better']:
        if value >= limit:
            return tone
    return 'bad'


def colour(tone):
    return TONES.get(tone or 'muted', NEUTRAL)


_FONT_CACHE = {}


def ui_font(size=10, weight='normal'):
    """A sans font that actually exists here.

    Tk substitutes silently for an unknown family, which on some systems
    lands on a serif face that looks nothing like the rest of the GUI.
    """
    key = (size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        families = set(tkfont.families())
    except Exception:
        families = set()
    for name in ('Segoe UI', 'Helvetica Neue', 'DejaVu Sans', 'Arial',
                 'Helvetica'):
        if name in families:
            _FONT_CACHE[key] = (name, size, weight)
            return _FONT_CACHE[key]
    _FONT_CACHE[key] = ('TkDefaultFont', size, weight)
    return _FONT_CACHE[key]


def mono_font(size=9, weight='normal'):
    try:
        families = set(tkfont.families())
    except Exception:
        families = set()
    for name in ('Cascadia Mono', 'Consolas', 'DejaVu Sans Mono',
                 'Liberation Mono', 'Courier New'):
        if name in families:
            return (name, size, weight)
    return ('TkFixedFont', size, weight)


class ReportView(tk.Frame):
    """Scrollable, read-only report canvas built from widgets."""

    def __init__(self, parent, padding=18, **kwargs):
        super().__init__(parent, bg=PAGE_BG, **kwargs)
        self._lines = []
        self._frozen = False
        self._rules = []

        self._canvas = tk.Canvas(self, bg=PAGE_BG, highlightthickness=0,
                                 bd=0)
        self._scroll = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                     command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        # Scrollbar first: the canvas must not claim its width.
        self._scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.body = tk.Frame(self._canvas, bg=PAGE_BG,
                             padx=padding, pady=padding)
        self._window = self._canvas.create_window(
            (0, 0), window=self.body, anchor='nw')

        self.body.bind('<Configure>', self._on_body_configure)
        self._canvas.bind('<Configure>', self._on_canvas_configure)
        self._bind_wheel()

    # ── Scrolling plumbing ──────────────────────────────────────────

    def _on_body_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        # Stretch the inner frame to the canvas width so rules and bars
        # span the full report rather than hugging their text.
        self._canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self):
        def on_wheel(event):
            if event.num == 5 or event.delta < 0:
                self._canvas.yview_scroll(1, 'units')
            elif event.num == 4 or event.delta > 0:
                self._canvas.yview_scroll(-1, 'units')

        def bind_all(_e=None):
            self._canvas.bind_all('<MouseWheel>', on_wheel)
            self._canvas.bind_all('<Button-4>', on_wheel)
            self._canvas.bind_all('<Button-5>', on_wheel)

        def unbind_all(_e=None):
            for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                try:
                    self._canvas.unbind_all(seq)
                except tk.TclError:
                    pass

        # bind_all is global, so claim it only while the pointer is over
        # this report — otherwise two open reports fight over the wheel.
        self._canvas.bind('<Enter>', bind_all)
        self._canvas.bind('<Leave>', unbind_all)
        self.bind('<Destroy>', unbind_all, add='+')

    # ── Text transcript ─────────────────────────────────────────────

    def _record(self, line=''):
        self._lines.append(line)

    def to_text(self):
        """The report as plain text, for export and email bodies."""
        return '\n'.join(self._lines)

    # ── Builders ────────────────────────────────────────────────────

    def title(self, text, subtitle=None):
        band = tk.Frame(self.body, bg=HEADER_BG)
        band.pack(fill=tk.X, pady=(0, 14))
        tk.Label(band, text=text, bg=HEADER_BG, fg='white',
                 font=ui_font(15, 'bold'), anchor='w'
                 ).pack(fill=tk.X, padx=16, pady=(12, 0 if subtitle else 12))
        if subtitle:
            tk.Label(band, text=subtitle, bg=HEADER_BG, fg='#BDC3C7',
                     font=ui_font(9), anchor='w'
                     ).pack(fill=tk.X, padx=16, pady=(2, 12))
        self._record(text.upper())
        if subtitle:
            self._record(subtitle)
        self._record()
        return self

    def section(self, text):
        wrap = tk.Frame(self.body, bg=PAGE_BG)
        wrap.pack(fill=tk.X, pady=(14, 6))
        tk.Label(wrap, text=text, bg=PAGE_BG, fg=ACCENT,
                 font=ui_font(11, 'bold'), anchor='w').pack(fill=tk.X)
        rule = tk.Frame(wrap, bg=RULE, height=1)
        rule.pack(fill=tk.X, pady=(4, 0))
        self._record()
        self._record(text.upper())
        self._record('=' * max(len(text), 3))
        return self

    def note(self, text, tone='muted'):
        tk.Label(self.body, text=text, bg=PAGE_BG, fg=colour(tone),
                 font=ui_font(9), anchor='w', justify=tk.LEFT,
                 wraplength=760).pack(fill=tk.X, pady=(2, 4))
        self._record(text)
        return self

    def scorecard(self, tiles):
        """A row of headline stat tiles: ``[(caption, value, tone), ...]``.

        The one thing a reader should see before anything else, so it
        goes at the top of a report rather than being buried in a list
        of key/value rows.
        """
        row = tk.Frame(self.body, bg=PAGE_BG)
        row.pack(fill=tk.X, pady=(4, 6))
        for index, tile in enumerate(tiles):
            caption, value = tile[0], tile[1]
            tone = tile[2] if len(tile) > 2 else 'info'
            card = tk.Frame(row, bg=CARD_BG, highlightthickness=1,
                            highlightbackground=RULE)
            card.grid(row=0, column=index, sticky='nsew', padx=(0, 8))
            row.grid_columnconfigure(index, weight=1, uniform='tile')
            tk.Frame(card, bg=colour(tone), height=3).pack(fill=tk.X)
            tk.Label(card, text=str(value), bg=CARD_BG, fg=colour(tone),
                     font=ui_font(18, 'bold'), anchor='w'
                     ).pack(fill=tk.X, padx=12, pady=(8, 0))
            tk.Label(card, text=caption, bg=CARD_BG, fg=TEXT_MUTED,
                     font=ui_font(8), anchor='w', wraplength=150,
                     justify=tk.LEFT).pack(fill=tk.X, padx=12, pady=(0, 10))
            self._record(f"{caption}: {value}")
        return self

    def kv(self, label, value, tone=None):
        """An aligned label/value row."""
        row = tk.Frame(self.body, bg=PAGE_BG)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=label, bg=PAGE_BG, fg=TEXT_MUTED,
                 font=ui_font(9), anchor='w').pack(side=tk.LEFT)
        tk.Label(row, text=str(value), bg=PAGE_BG,
                 fg=colour(tone) if tone else TEXT,
                 font=ui_font(9, 'bold'), anchor='e').pack(side=tk.RIGHT)
        self._record(f"{label}: {value}")
        return self

    def metric(self, label, value, pct=None, tone=None,
               direction='higher_better'):
        """A label, a value, and a bar showing ``pct`` of the way across.

        ``direction`` decides what "good" means — see the module
        docstring. Pass ``tone`` to override the automatic choice.
        """
        if tone is None:
            tone = tone_for(pct, direction)
        fill = colour(tone)

        row = tk.Frame(self.body, bg=PAGE_BG)
        row.pack(fill=tk.X, pady=3)

        head = tk.Frame(row, bg=PAGE_BG)
        head.pack(fill=tk.X)
        tk.Label(head, text=label, bg=PAGE_BG, fg=TEXT, font=ui_font(9),
                 anchor='w').pack(side=tk.LEFT)
        tk.Label(head, text=str(value), bg=PAGE_BG, fg=fill,
                 font=ui_font(9, 'bold'), anchor='e').pack(side=tk.RIGHT)

        if pct is not None:
            try:
                fraction = max(0.0, min(1.0, float(pct) / 100.0))
            except (TypeError, ValueError):
                fraction = 0.0
            track = tk.Frame(row, bg=TRACK, height=6)
            track.pack(fill=tk.X, pady=(3, 0))
            track.pack_propagate(False)
            bar = tk.Frame(track, bg=fill, height=6)
            # place with relwidth so the bar tracks the window as it
            # resizes; a fixed pixel width would be wrong the moment
            # anybody drags the dialog.
            bar.place(x=0, y=0, relwidth=fraction, relheight=1.0)
            self._record(f"{label}: {value}  [{'#' * int(fraction * 20):<20}]")
        else:
            self._record(f"{label}: {value}")
        return self

    def bullet(self, text, tone='muted', bold=False):
        row = tk.Frame(self.body, bg=PAGE_BG)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text='●', bg=PAGE_BG, fg=colour(tone),
                 font=ui_font(7)).pack(side=tk.LEFT, padx=(2, 7), anchor='n',
                                       pady=3)
        tk.Label(row, text=text, bg=PAGE_BG, fg=TEXT,
                 font=ui_font(9, 'bold' if bold else 'normal'),
                 anchor='w', justify=tk.LEFT, wraplength=720
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._record(f"  • {text}")
        return self

    def item(self, headline, tone='info', detail=None, meta=None):
        """A card for a finding: coloured spine, headline, detail, meta."""
        card = tk.Frame(self.body, bg=CARD_BG, highlightthickness=1,
                        highlightbackground=RULE)
        card.pack(fill=tk.X, pady=(0, 6))
        tk.Frame(card, bg=colour(tone), width=4).pack(side=tk.LEFT, fill=tk.Y)
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=11, pady=8)
        tk.Label(inner, text=headline, bg=CARD_BG, fg=TEXT,
                 font=ui_font(10, 'bold'), anchor='w', justify=tk.LEFT,
                 wraplength=700).pack(fill=tk.X)
        self._record(f"  • {headline}")
        if detail:
            tk.Label(inner, text=detail, bg=CARD_BG, fg=TEXT_MUTED,
                     font=ui_font(9), anchor='w', justify=tk.LEFT,
                     wraplength=700).pack(fill=tk.X, pady=(3, 0))
            self._record(f"      {detail}")
        if meta:
            tk.Label(inner, text=meta, bg=CARD_BG, fg=TEXT_MUTED,
                     font=ui_font(8), anchor='w').pack(fill=tk.X, pady=(4, 0))
            self._record(f"      {meta}")
        return self

    def pill_row(self, pills):
        """A row of small coloured badges: ``[(text, tone), ...]``."""
        row = tk.Frame(self.body, bg=PAGE_BG)
        row.pack(fill=tk.X, pady=(2, 6))
        for text, tone in pills:
            tk.Label(row, text=f" {text} ", bg=colour(tone), fg='white',
                     font=ui_font(8, 'bold')).pack(side=tk.LEFT, padx=(0, 6))
        self._record('  ' + '  '.join(f"[{t}]" for t, _ in pills))
        return self

    def table(self, headers, rows, height=None):
        """A banded table. Falls back to nothing when there are no rows."""
        if not rows:
            return self.note('—')
        wrap = tk.Frame(self.body, bg=CARD_BG, highlightthickness=1,
                        highlightbackground=RULE)
        wrap.pack(fill=tk.X, pady=(2, 6))
        tree = ttk.Treeview(wrap, columns=list(range(len(headers))),
                            show='headings',
                            height=height or min(len(rows), 12))
        for index, header in enumerate(headers):
            tree.heading(index, text=header)
            tree.column(index, width=140,
                        anchor='w' if index == 0 else 'e')
        tree.tag_configure('odd', background='#F7F9FA')
        tree.tag_configure('even', background=CARD_BG)
        for index, row in enumerate(rows):
            tree.insert('', 'end', values=[str(c) for c in row],
                        tags=('odd' if index % 2 else 'even',))
        tree.pack(fill=tk.X, padx=1, pady=1)
        self._record('  ' + ' | '.join(str(h) for h in headers))
        for row in rows:
            self._record('  ' + ' | '.join(str(c) for c in row))
        return self

    def distribution(self, pairs, total=None):
        """Named counts as proportional bars — a share is a length.

        ``pairs`` is ``[(name, count), ...]``. Percentages are of
        ``total`` when given, otherwise of the sum.
        """
        items = list(pairs)
        if not items:
            return self.note('—')
        denominator = total if total else sum(c for _, c in items) or 1
        biggest = max((c for _, c in items), default=0) or 1
        for name, count in items:
            share = (count / denominator) * 100
            # Scale bars against the largest entry so a long tail is
            # still visible; the label carries the true percentage.
            self.metric(str(name), f"{count:,} ({share:.1f}%)",
                        (count / biggest) * 100, tone='accent')
        return self

    def spacer(self, height=8):
        tk.Frame(self.body, bg=PAGE_BG, height=height).pack(fill=tk.X)
        return self

    def empty(self, text):
        box = tk.Frame(self.body, bg=CARD_BG, highlightthickness=1,
                       highlightbackground=RULE)
        box.pack(fill=tk.X, pady=8)
        tk.Label(box, text=text, bg=CARD_BG, fg=TEXT_MUTED,
                 font=ui_font(10)).pack(pady=22)
        self._record(text)
        return self

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()
        self._lines = []
        self._frozen = False
        return self

    def freeze(self):
        """Finish building. Scrolls back to the top."""
        self._frozen = True
        self.body.update_idletasks()
        self._on_body_configure()
        try:
            self._canvas.yview_moveto(0)
        except tk.TclError:
            pass
        return self


def report_toolbar(parent, view, extra=None):
    """A footer with Copy / Save-as-text, plus any ``extra`` buttons.

    Reports were previously read-only dead ends — you could look at the
    numbers and nothing else. Copy and Save work off
    :meth:`ReportView.to_text`, so they keep working for any report
    built with these helpers.
    """
    bar = tk.Frame(parent, bg=PAGE_BG)

    def copy():
        try:
            parent.clipboard_clear()
            parent.clipboard_append(view.to_text())
        except tk.TclError:
            logger.debug("Clipboard unavailable", exc_info=True)

    def save():
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Save report", defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(view.to_text())
        except OSError as exc:
            logger.error("Failed to save report: %s", exc)

    for label, command in (("Copy", copy), ("Save as text…", save)):
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT,
                                                          padx=(0, 8))
    for label, command in (extra or []):
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT,
                                                          padx=(0, 8))
    return bar


# ── Text-report adapter ─────────────────────────────────────────────

_RULE_RE = re.compile(r'^\s*[=\-_~*]{3,}\s*$')
_ASCII_BAR_RE = re.compile(r'\s*[\[(][#=\-. █░]{4,}[\])]\s*$')
_KV_RE = re.compile(r'^\s*(?P<label>[^:]{1,60}?)\s*:\s*(?P<value>.*\S)\s*$')
_BULLET_RE = re.compile(r'^\s*(?:[•●*]|-(?!-))\s+(?P<text>.+)$')
_PERCENT_RE = re.compile(r'(?P<pct>\d{1,3}(?:\.\d+)?)\s*%')
_NUMBERED_RE = re.compile(r'^\s*\d+[.)]\s+(?P<text>.+)$')

#: Words that make a "Label: value" row a problem rather than a fact, so
#: it can be toned red instead of neutral.
_BAD_WORDS = ('overdue', 'failed', 'error', 'missing', 'outstanding',
              'breach', 'critical', 'rejected', 'unpaid', 'arrears')
_GOOD_WORDS = ('paid', 'collected', 'complete', 'compliant', 'approved',
               'resolved', 'active', 'success')


def _looks_like_heading(line, next_line):
    stripped = line.strip()
    if not stripped or len(stripped) > 70:
        return False
    if next_line is not None and _RULE_RE.match(next_line):
        return True
    # ALL CAPS with no trailing colon-value is the house section style.
    letters = [c for c in stripped if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and ':' not in stripped:
        return True
    return False


def render_text(view, text, title=None):
    """Render a house-style plain-text report into a :class:`ReportView`.

    This is a **bridge, not the destination**. Reports across finance,
    student support and the IT helpdesk are built as formatted strings —
    ``'=' * 50`` rules, ``ALL CAPS`` section headers, ``Label: value``
    rows, ``[####----]`` ASCII bars. Rewriting every one of those
    generators to emit structured content is the right long-term fix;
    this recognises the conventions they already follow and draws them
    as real widgets, so every existing report gains the styling with one
    change at each display site.

    What it recognises:

    * a line of ``===`` / ``---`` under a short line -> section header
    * an ``ALL CAPS`` line with no colon -> section header
    * ``Label: value`` -> a key/value row, with a bar when the value is
      a percentage, and tone when the label reads good or bad
    * ``• item`` / ``- item`` / ``1. item`` -> a bullet
    * a trailing ``[####----]`` ASCII bar -> stripped, since the real
      bar replaces it

    Anything it does not recognise is emitted verbatim as a note, so no
    content is ever silently dropped. When a report matters enough to
    deserve better than this, render it structurally instead — see
    ``quality_manager.render_quality_report`` for what that looks like.
    """
    if not text:
        view.empty("No content.")
        return view

    lines = str(text).replace('\r\n', '\n').split('\n')
    # Strip the uniform leading indentation some reports are written with
    # inside triple-quoted strings.
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    trim = min(indents) if indents else 0
    lines = [l[trim:] if len(l) >= trim else l for l in lines]

    index = 0
    if title is not None:
        view.title(title)
    else:
        # First substantial line becomes the title. Skip leading blanks
        # *and* rules: several reports open with a full-width '=' banner
        # above the title, which would otherwise become the title.
        while index < len(lines) and (not lines[index].strip()
                                      or _RULE_RE.match(lines[index])):
            index += 1
        if index < len(lines):
            view.title(lines[index].strip())
            index += 1
            if index < len(lines) and _RULE_RE.match(lines[index]):
                index += 1

    pending_blank = False
    while index < len(lines):
        raw = lines[index]
        line = raw.rstrip()
        nxt = lines[index + 1] if index + 1 < len(lines) else None

        if not line.strip():
            pending_blank = True
            index += 1
            continue
        if _RULE_RE.match(line):
            index += 1
            continue

        if _looks_like_heading(line, nxt):
            view.section(line.strip().rstrip(':'))
            index += 1
            if nxt is not None and _RULE_RE.match(nxt):
                index += 1
            pending_blank = False
            continue

        if pending_blank:
            pending_blank = False

        # Strip a hand-drawn bar; the widget draws a real one.
        cleaned = _ASCII_BAR_RE.sub('', line).rstrip()

        bullet = _BULLET_RE.match(cleaned) or _NUMBERED_RE.match(cleaned)
        if bullet:
            body = bullet.group('text').strip()
            kv = _KV_RE.match(body)
            if kv and not _PERCENT_RE.search(kv.group('value')):
                view.kv(kv.group('label').strip(), kv.group('value').strip(),
                        tone=_tone_for_label(kv.group('label')))
            else:
                view.bullet(body, tone=_tone_for_label(body))
            index += 1
            continue

        kv = _KV_RE.match(cleaned)
        if kv:
            label = kv.group('label').strip()
            value = kv.group('value').strip()
            match = _PERCENT_RE.search(value)
            if match:
                try:
                    pct = float(match.group('pct'))
                except ValueError:
                    pct = None
                if pct is not None and 0 <= pct <= 100:
                    lowered = label.lower()
                    direction = ('lower_better'
                                 if any(w in lowered for w in _BAD_WORDS)
                                 else 'higher_better')
                    view.metric(label, value, pct, direction=direction)
                    index += 1
                    continue
            view.kv(label, value, tone=_tone_for_label(label))
            index += 1
            continue

        view.note(cleaned.strip(), tone='muted')
        index += 1

    return view


def _tone_for_label(label):
    lowered = str(label).lower()
    if any(word in lowered for word in _BAD_WORDS):
        return 'bad'
    if any(word in lowered for word in _GOOD_WORDS):
        return 'good'
    return None


class TextReportView(ReportView):
    """A ReportView that accepts text the way a ``Text`` widget did.

    Drop-in for a ``ScrolledText`` used purely for display: it answers to
    ``insert``, ``delete`` and ``get`` so existing report code keeps
    working, while rendering through :func:`render_text`. It is *not* an
    editor — ``insert`` replaces the whole report rather than splicing at
    an index, which is all the display sites ever did with it.
    """

    #: Geometry and typography options a Text accepts and a Frame does
    #: not. Dropped rather than passed through, so an existing call site
    #: needs no edit beyond the class name.
    _TEXT_ONLY_OPTIONS = ('font', 'height', 'width', 'wrap', 'state',
                          'yscrollcommand', 'xscrollcommand', 'undo',
                          'insertbackground', 'selectbackground',
                          'relief', 'borderwidth', 'bd', 'spacing1',
                          'spacing3', 'tabs')

    def __init__(self, parent, **kwargs):
        for option in self._TEXT_ONLY_OPTIONS:
            kwargs.pop(option, None)
        # A report background is the palette's, not the caller's.
        kwargs.pop('bg', None)
        kwargs.pop('background', None)
        super().__init__(parent, **kwargs)
        self._raw = ''

    def insert(self, _index, text, *_args):
        self._raw = (self._raw + str(text)) if self._raw else str(text)
        self.clear()
        render_text(self, self._raw)
        self.freeze()

    def delete(self, *_args):
        self._raw = ''
        self.clear()

    def get(self, *_args):
        return self._raw

    def config(self, **kwargs):
        # Display sites call config(state='disabled'); the view is always
        # read-only, so that is a no-op rather than an error.
        kwargs.pop('state', None)
        if kwargs:
            super().config(**kwargs)

    configure = config

    def to_text(self):
        return self._raw or super().to_text()

    # ── Text-widget API a display site may still call ──────────────
    # These exist so swapping a ScrolledText for this class needs no
    # other edits. They are no-ops where the concept does not apply
    # (styling tags, an insertion cursor) and delegate where it does.

    def tag_configure(self, *_args, **_kwargs):
        """No-op: tone and emphasis come from the renderer, not tags."""

    tag_config = tag_configure

    def tag_add(self, *_args, **_kwargs):
        """No-op — see :meth:`tag_configure`."""

    def tag_remove(self, *_args, **_kwargs):
        """No-op — see :meth:`tag_configure`."""

    def mark_set(self, *_args, **_kwargs):
        """No-op: there is no insertion cursor in a rendered report."""

    def see(self, *_args):
        """Scroll to the top; a rendered report has no text indices."""
        try:
            self._canvas.yview_moveto(0)
        except tk.TclError:
            logger.debug("Could not scroll the report", exc_info=True)

    def yview(self, *args):
        return self._canvas.yview(*args)

    def yview_moveto(self, fraction):
        return self._canvas.yview_moveto(fraction)

    def index(self, *_args):
        return '1.0'

    def edit_reset(self, *_args, **_kwargs):
        """No-op: the view is read-only, so there is no undo stack."""
