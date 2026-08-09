"""Restructure the merged platform document into four clearly separated parts.

Input is the extracted block list from the merged PROGRAM_OVERVIEW.docx (see
extract_overview.py) plus the generated inventory. Output is a single document:

    Front matter          cover · document information · contents · how to use
    Part I    (1-8)       Platform Overview
    Part II   (9-17)      User and Administration Guide
    Part III  (18-24)     Technical Reference
    Part IV   (25-29)     Supporting Information

Sections are numbered continuously, so a cross-reference like 10.4 or 14.5 is
unambiguous anywhere in the file.

    python build_combined.py overview.json inventory.json out.docx [figdir]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import docx
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt, RGBColor

# ── part palette ───────────────────────────────────────────────────────
NAVY = RGBColor(0x1B, 0x2A, 0x4A)      # Part I   — Platform Overview
BLUE = RGBColor(0x1F, 0x4E, 0x8C)      # Part II  — User and Administration
SLATE = RGBColor(0x44, 0x4F, 0x5A)     # Part III — Technical Reference
TEAL = RGBColor(0x11, 0x4B, 0x4B)      # Part IV  — Supporting Information
INK = RGBColor(0x0B, 0x0B, 0x0B)
GREY = RGBColor(0x55, 0x55, 0x55)
MUTED = RGBColor(0x89, 0x87, 0x81)
RED = RGBColor(0xC0, 0x39, 0x2B)

PARTS = [
    ("I", "Platform Overview", NAVY, "1B2A4A",
     "What the platform is, how it is put together, and what it does — for "
     "managers, governors and anyone evaluating it."),
    ("II", "User and Administration Guide", BLUE, "1F4E8C",
     "How to install, secure, operate and administer the platform, step by "
     "step — for everyday users and administrators."),
    ("III", "Technical Reference", SLATE, "444F5A",
     "Every endpoint the running server publishes, generated from its own "
     "routing table — for developers and integrators."),
    ("IV", "Supporting Information", TEAL, "114B4B",
     "Glossary, indexes, licence and where to find the source."),
]

FIGURES = [
    "fig-platform", "fig-composition", "fig-signin", "fig-identity",
    "fig-token", "fig-layers", "fig-cli-vs-gui", "fig-api-surface",
    "fig-menu-nursery", "fig-menu-primary", "fig-menu-secondary",
    "fig-menu-sixth_form", "fig-university-domains", "fig-progression",
]

SYSTEMS = [
    ("nursery", "Nursery / Early Years", "nursery"),
    ("primary", "Primary School", "primary"),
    ("secondary", "Secondary School", "school"),
    ("sixth_form", "Sixth Form College", "sixthform"),
    ("university", "University", "university"),
]


# ══════════════════════════════════════════════════════════════════════
# low-level Word plumbing
# ══════════════════════════════════════════════════════════════════════
def field(paragraph, instr, placeholder="", size=None, colour=None, bold=False):
    """Insert a Word field code (TOC, PAGE, STYLEREF, SEQ, …)."""
    r = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    r._r.append(fld)

    r = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)

    r = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "separate")
    r._r.append(fld)

    r = paragraph.add_run(placeholder)
    if size:
        r.font.size = size
    if colour is not None:
        r.font.color.rgb = colour
    r.bold = bold

    r2 = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "end")
    r2._r.append(fld)
    return paragraph


def bookmark(paragraph, name, bid):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bid))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bid))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def internal_link(paragraph, anchor, text, size=Pt(8), colour=None):
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), anchor)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    if colour is not None:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), f"{colour:06X}" if isinstance(colour, int)
              else str(colour))
        rPr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size.pt * 2)))
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    link.append(r)
    paragraph._p.append(link)


def shade(el, hex_fill):
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hex_fill)
    el.append(sh)


def repeat_header_row(table):
    """Mark row 0 as a header so it repeats on every page the table spans."""
    tr = table.rows[0]._tr
    trPr = tr.get_or_add_trPr()
    h = OxmlElement("w:tblHeader")
    h.set(qn("w:val"), "true")
    trPr.append(h)
    # and keep header rows from splitting mid-row
    cant = OxmlElement("w:cantSplit")
    trPr.append(cant)


def set_cell_bg(cell, hex_fill):
    shade(cell._tc.get_or_add_tcPr(), hex_fill)


# ══════════════════════════════════════════════════════════════════════
class Book:
    def __init__(self, figdir):
        self.figdir = Path(figdir)
        self.doc = docx.Document()
        self.bid = 1000
        self.shots = []
        self.figs = []
        self._styles()
        self._page()

    # ── setup ────────────────────────────────────────────────────────
    def _page(self):
        for s in self.doc.sections:
            s.page_width = Inches(8.27)
            s.page_height = Inches(11.69)
            s.left_margin = s.right_margin = Inches(0.85)
            s.top_margin = Inches(0.8)
            s.bottom_margin = Inches(0.8)
            s.header_distance = Inches(0.4)
            s.footer_distance = Inches(0.4)

    def _styles(self):
        st = self.doc.styles
        n = st["Normal"]
        n.font.name = "Calibri"
        n.font.size = Pt(10.5)
        n.paragraph_format.space_after = Pt(6)
        n.paragraph_format.line_spacing = 1.12
        for name, size, colour, before in [
            ("Heading 1", 19, NAVY, 22),
            ("Heading 2", 14, BLUE, 14),
            ("Heading 3", 11.5, BLUE, 10),
            ("Heading 4", 10.5, SLATE, 8),
        ]:
            s = st[name]
            s.font.name = "Calibri"
            s.font.size = Pt(size)
            s.font.color.rgb = colour
            s.font.bold = True
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(4)
            s.paragraph_format.keep_with_next = True
        st["Heading 1"].paragraph_format.page_break_before = True

        cap = st["Caption"]
        cap.font.name = "Calibri"
        cap.font.size = Pt(8.5)
        cap.font.color.rgb = GREY
        cap.font.italic = False
        cap.paragraph_format.space_after = Pt(10)
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # a style the running header can point at for the current part
        try:
            part = st.add_style("Part Title", 1)
        except Exception:
            part = st["Part Title"]
        part.font.name = "Calibri"
        part.font.size = Pt(30)
        part.font.bold = True
        part.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        part.paragraph_format.space_after = Pt(0)
        self.part_style = part

    # ── primitives ───────────────────────────────────────────────────
    def p(self, text="", style=None):
        return self.doc.add_paragraph(text, style=style)

    def h(self, text, level, anchor=None):
        para = self.doc.add_paragraph(text, style=f"Heading {level}")
        if level <= 2:
            self.bid += 1
            name = anchor or ("s" + re.sub(r"\W+", "_", text)[:38])
            bookmark(para, name, self.bid)
            if level == 1:
                self._back_link()
        return para

    def _back_link(self):
        para = self.p()
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(10)
        internal_link(para, "_Contents", "↑ Back to contents",
                      size=Pt(8), colour="1F4E8C")

    def bullet(self, text):
        return self.doc.add_paragraph(text, style="List Bullet")

    def note(self, text, lead="Note"):
        para = self.p()
        para.paragraph_format.left_indent = Pt(14)
        r = para.add_run(f"{lead}: ")
        r.bold = True
        r.italic = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = GREY
        r = para.add_run(text)
        r.italic = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = GREY
        return para

    def code(self, text):
        para = self.p()
        para.paragraph_format.space_after = Pt(1)
        para.paragraph_format.left_indent = Pt(20)
        r = para.add_run(text)
        r.font.name = "Consolas"
        r.font.size = Pt(9)
        return para

    def lead_para(self, lead, text):
        para = self.p()
        r = para.add_run(lead)
        r.bold = True
        r.font.size = Pt(9)
        r = para.add_run(text)
        r.font.size = Pt(9)
        return para

    def table(self, rows, small=False, header=True, widths=None):
        if not rows:
            return None
        cols = max(len(r) for r in rows)
        t = self.doc.add_table(rows=0, cols=cols)
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        size = Pt(8) if small else Pt(9.5)
        for i, row in enumerate(rows):
            cells = t.add_row().cells
            for cell, value in zip(cells, list(row) + [""] * (cols - len(row))):
                para = cell.paragraphs[0]
                para.paragraph_format.space_after = Pt(1)
                r = para.add_run(str(value))
                r.font.size = size
                if i == 0 and header:
                    r.bold = True
        if header:
            repeat_header_row(t)
        if widths:
            for row in t.rows:
                for cell, w in zip(row.cells, widths):
                    cell.width = Inches(w)
        self.p().paragraph_format.space_after = Pt(4)
        return t

    # ── captions with SEQ fields (so Word can build the lists) ────────
    def figure(self, name, caption, width=6.2, path=None):
        path = Path(path) if path else self.figdir / f"{name}.png"
        if not path.exists():
            return
        para = self.p()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(8)
        para.paragraph_format.space_after = Pt(2)
        para.add_run().add_picture(str(path), width=Inches(width))

        cap = self.p(style="Caption")
        r = cap.add_run("Figure ")
        r.bold = True
        field(cap, "SEQ Figure \\* ARABIC", str(len(self.figs) + 1),
              size=Pt(8.5), bold=True)
        r = cap.add_run(". " + caption)
        r.font.size = Pt(8.5)
        self.figs.append(caption)

    def shot(self, title, capture, filename, shows=None):
        n = len(self.shots) + 1
        cap = self.p(style="Caption")
        cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cap.paragraph_format.space_after = Pt(2)
        r = cap.add_run("Screenshot ")
        r.bold = True
        r.font.color.rgb = NAVY
        field(cap, "SEQ Screenshot \\* ARABIC", str(n), size=Pt(8.5),
              colour=NAVY, bold=True)
        r = cap.add_run(" — " + title)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = NAVY

        t = self.doc.add_table(rows=1, cols=1)
        t.style = "Table Grid"
        cell = t.rows[0].cells[0]
        q = cell.paragraphs[0]
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        q.paragraph_format.space_after = Pt(2)
        r = q.add_run("[  SCREENSHOT GOES HERE  ]")
        r.bold = True
        r.font.color.rgb = RED
        r.font.size = Pt(9.5)
        q = cell.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        q.paragraph_format.space_after = Pt(2)
        r = q.add_run("Capture: ")
        r.bold = True
        r.font.size = Pt(8.5)
        r = q.add_run(capture)
        r.font.size = Pt(8.5)
        if filename:
            q = cell.add_paragraph()
            q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            q.paragraph_format.space_after = Pt(2)
            r = q.add_run(filename)
            r.font.name = "Consolas"
            r.font.size = Pt(7.5)
            r.font.color.rgb = MUTED
        if shows:
            self.lead_para("What this shows: ", shows)
        self.p().paragraph_format.space_after = Pt(4)
        self.shots.append(title)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ── divider pages ────────────────────────────────────────────────
    def divider(self, numeral, title, colour, fill, blurb, contents):
        """A full-page coloured divider — a page-sized shaded table cell."""
        self.doc.add_section(WD_SECTION.NEW_PAGE)
        self._page()
        sec = self.doc.sections[-1]
        sec.different_first_page_header_footer = True

        t = self.doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = t.rows[0].cells[0]
        cell.width = Inches(6.57)
        set_cell_bg(cell, fill)
        tcPr = cell._tc.get_or_add_tcPr()
        h = OxmlElement("w:tcW")
        h.set(qn("w:w"), str(int(6.57 * 1440)))
        h.set(qn("w:type"), "dxa")
        tcPr.append(h)

        pad = cell.paragraphs[0]
        pad.paragraph_format.space_before = Pt(150)
        pad.paragraph_format.space_after = Pt(0)

        q = cell.add_paragraph()
        q.paragraph_format.space_after = Pt(4)
        r = q.add_run(f"Part {numeral}")
        r.font.size = Pt(13)
        r.font.color.rgb = RGBColor(0xD8, 0xDE, 0xE8)
        r.bold = True

        q = cell.add_paragraph(style="Part Title")
        q.add_run(title)

        q = cell.add_paragraph()
        q.paragraph_format.space_before = Pt(10)
        r = q.add_run(blurb)
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0xD8, 0xDE, 0xE8)

        q = cell.add_paragraph()
        q.paragraph_format.space_before = Pt(26)
        r = q.add_run("In this part")
        r.font.size = Pt(9)
        r.bold = True
        r.font.color.rgb = RGBColor(0xA9, 0xB6, 0xCC)
        for line in contents:
            q = cell.add_paragraph()
            q.paragraph_format.space_after = Pt(1)
            r = q.add_run(line)
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        q = cell.add_paragraph()
        q.paragraph_format.space_before = Pt(150)

        # body pages after the divider return to a normal running header
        self.doc.add_section(WD_SECTION.NEW_PAGE)
        self._page()
        self._running_header(self.doc.sections[-1])
        self._footer(self.doc.sections[-1])

    def _running_header(self, section):
        section.header.is_linked_to_previous = False
        p = section.header.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        tabs = p.paragraph_format.tab_stops
        tabs.add_tab_stop(Inches(6.57), 2)  # right-aligned
        field(p, 'STYLEREF "Part Title" \\* MERGEFORMAT', "", size=Pt(8),
              colour=MUTED)
        p.add_run("\t")
        field(p, 'STYLEREF "Heading 1" \\* MERGEFORMAT', "", size=Pt(8),
              colour=MUTED)
        for r in p.runs:
            r.font.size = Pt(8)
            r.font.color.rgb = MUTED
        pPr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "2")
        bottom.set(qn("w:color"), "D8D8D4")
        bdr.append(bottom)
        pPr.append(bdr)

    def _footer(self, section):
        section.footer.is_linked_to_previous = False
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        field(p, "PAGE", "1", size=Pt(8.5), colour=GREY)


# ══════════════════════════════════════════════════════════════════════
# block replay
# ══════════════════════════════════════════════════════════════════════
NUM_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)*|[A-E])[.)]?\s+")
SHOT_HEAD = re.compile(r"^Screenshot\s+\d+\s*[—–-]\s*(.*)$")
IFACE_HEAD = re.compile(r"—\s*(command line|desktop application|REST API|"
                        r"on the command line|in the desktop application|"
                        r"over the API)\s*$", re.I)


def parse_placeholder(text):
    """Pull title/capture/filename back out of an extracted placeholder box."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    capture, fname = "", ""
    for ln in lines:
        if ln.lower().startswith("capture:"):
            capture = ln.split(":", 1)[1].strip()
        elif ln.lower().startswith("save as:"):
            fname = ln.split(":", 1)[1].strip()
        elif ln.startswith("assets/"):
            fname = ln
        elif ln.startswith("[ SCREENSHOT") and "]" in ln:
            rest = ln.split("]", 1)[1].strip()
            if rest.startswith("—"):
                rest = rest[1:].strip()
            if rest and " — " in rest:
                title, cap = rest.split(" — ", 1)
                capture = capture or cap
    return capture, fname


class Replayer:
    """Replays extracted blocks under new, continuously numbered headings."""

    def __init__(self, book, blocks):
        self.b = book
        self.blocks = blocks
        self.index = {}
        for i, blk in enumerate(blocks):
            if blk["kind"] in ("h1", "h2", "h3"):
                self.index.setdefault(blk["text"], []).append(i)

    def find(self, text, occurrence=0):
        return self.index[text][occurrence]

    def span(self, start_text, end_text, s_occ=0, e_occ=0):
        return self.find(start_text, s_occ), self.find(end_text, e_occ)

    def emit(self, lo, hi, section_no, *, skip_interface=False,
             skip_kinds=(), heading_shift=0, drop_shots=False,
             sub=None, figure_after=None, drop_headings=()):
        """Replay blocks [lo, hi) beneath section `section_no`."""
        sub = sub if sub is not None else [0, 0]
        skipping_until_level = None
        pending_shot = None
        for blk in self.blocks[lo:hi]:
            kind = blk["kind"]
            text = blk.get("text", "")

            if kind in ("h1", "h2", "h3", "h4"):
                level = int(kind[1])
                if skipping_until_level is not None:
                    if level <= skipping_until_level:
                        skipping_until_level = None
                    else:
                        continue
                if skip_interface and level == 3 and IFACE_HEAD.search(text):
                    skipping_until_level = 3
                    continue
                m = SHOT_HEAD.match(text)
                if m:
                    if drop_shots:
                        skipping_until_level = level
                        continue
                    pending_shot = m.group(1)
                    continue
                clean = NUM_PREFIX.sub("", text).strip()
                if clean in drop_headings:
                    continue
                fig = (figure_after or {}).get(clean)
                if level == 2 + heading_shift:
                    sub[0] += 1
                    sub[1] = 0
                    self.b.h(f"{section_no}.{sub[0]} {clean}", 2)
                elif level == 3 + heading_shift:
                    sub[1] += 1
                    self.b.h(f"{section_no}.{sub[0]}.{sub[1]} {clean}", 3)
                else:
                    self.b.h(clean, 4)
                if fig:
                    self.b.figure(*fig)
                continue

            if skipping_until_level is not None:
                continue
            if kind in skip_kinds:
                continue

            if kind == "placeholder":
                if drop_shots:
                    pending_shot = None
                    continue
                capture, fname = parse_placeholder(text)
                self.b.shot(pending_shot or "Screenshot", capture, fname)
                pending_shot = None
            elif kind == "table":
                self.b.table(blk["rows"], small=len(blk["rows"]) > 8)
            elif kind == "code":
                self.b.code(text)
            elif kind == "note":
                if text.startswith("Figure 1 —"):
                    self.b.figure(
                        "architecture",
                        text.split("—", 1)[1].strip(),
                        path=self.b.figdir.parent / "architecture.png")
                    continue
                self.b.note(text, lead="Note")
            elif kind == "bullet":
                self.b.bullet(text)
            else:
                lead = blk.get("lead")
                if lead and lead.startswith("Figure "):
                    continue          # captions are re-emitted with the image
                if lead:
                    self.b.lead_para(lead, text)
                else:
                    self.b.p(text)
        return sub


# ══════════════════════════════════════════════════════════════════════
# front matter
# ══════════════════════════════════════════════════════════════════════
def front_matter(b: Book):
    sec = b.doc.sections[0]
    sec.different_first_page_header_footer = True

    # ── cover ────────────────────────────────────────────────────────
    for _ in range(3):
        b.p()
    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("Education Management Platform")
    r.bold = True
    r.font.size = Pt(32)
    r.font.color.rgb = NAVY

    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("Overview, User Guide and Technical Reference")
    r.font.size = Pt(15)
    r.font.color.rgb = GREY

    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.paragraph_format.space_before = Pt(18)
    for line, size, colour in [
        ("Nursery · Primary · Secondary · Sixth Form · University", 11, INK),
        ("Command line · desktop application · REST API", 11, INK),
    ]:
        qq = b.p()
        qq.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = qq.add_run(line)
        rr.font.size = Pt(size)
        rr.font.color.rgb = colour

    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.paragraph_format.space_before = Pt(40)
    r = q.add_run("Version 9.7.0")
    r.font.size = Pt(12)
    r.bold = True
    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("28 July 2026")
    r.font.size = Pt(11)
    r.font.color.rgb = GREY
    q = b.p()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("https://github.com/sean1352636/university_system")
    r.font.size = Pt(10)
    r.font.color.rgb = GREY
    b.page_break()

    # ── document information ─────────────────────────────────────────
    b.h("Document information", 1, anchor="_DocInfo")
    b.table([
        ["Field", "Value"],
        ["Title", "Education Management Platform — Overview, User Guide and "
                  "Technical Reference"],
        ["Platform version", "9.7.0"],
        ["Document date", "28 July 2026"],
        ["Status", "Draft — screenshot placeholders not yet replaced"],
        ["Audience", "Managers and evaluators · everyday users · administrators · "
                     "developers and integrators"],
        ["Structure", "Four parts, sections numbered continuously 1–29"],
        ["Owner", "Not yet assigned"],
        ["Review date", "Not yet set"],
        ["Source", "github.com/sean1352636/university_system"],
    ], widths=[1.5, 5.0])

    b.h("How this document was produced", 2)
    b.p(
        "Part I and Part II are written. Part III, and every menu listing in "
        "section 14, are generated directly from the software — the menu tables "
        "from the navigation definitions the application reads at startup, and "
        "the endpoint tables from the running server's own routing table. They "
        "are not transcribed, so they cannot drift from the code by hand-editing."
    )
    b.p(
        "Counts and statistics were measured on the document date. Where the "
        "project's own documentation records a limitation, that wording was "
        "preferred over a more flattering summary."
    )

    b.h("Draft status", 2)
    q = b.p()
    q.paragraph_format.left_indent = Pt(10)
    r = q.add_run("This document is a draft. Before it is circulated:")
    r.bold = True
    r.font.color.rgb = RED
    for item in [
        "Replace every bordered screenshot placeholder, or delete the empty "
        "slots and their captions.",
        "Update the fields so the contents list, figure list, screenshot list "
        "and page numbers populate — select all (Ctrl+A) and press F9, "
        "choosing “update entire table” when prompted.",
        "Decide whether the development-credentials table in section 3 and the "
        "live account statistics belong in the copy you are sending.",
        "Assign an owner and a review date on the page above.",
    ]:
        qq = b.bullet(item)
        for r in qq.runs:
            r.font.color.rgb = RED
            r.font.size = Pt(9.5)
    b.p()
    b.note(
        "Screenshots must use demonstration data only. This platform holds "
        "records about children, and an image travels further than a database "
        "export because it ends up embedded in a document that gets forwarded "
        "and printed.", lead="Data protection")

    # ── contents ─────────────────────────────────────────────────────
    b.h("Contents", 1, anchor="_Contents")
    b.p(
        "This list is a Word field. If it is empty or out of date, click it and "
        "press F9, or select all and press F9, to rebuild it with page numbers."
    )
    q = b.p()
    field(q, 'TOC \\o "1-2" \\h \\z \\u',
          "Right-click and choose “Update field” to build the contents list.")

    b.h("Figures", 1, anchor="_Figures")
    q = b.p()
    field(q, 'TOC \\h \\z \\c "Figure"',
          "Update this field to list the figures.")

    b.h("Screenshots", 1, anchor="_Screenshots")
    b.p(
        "Every screenshot slot in the document, in order. Capture by interface "
        "rather than by system — all the command lines in one sitting, then all "
        "the desktop applications, then the API documentation page once."
    )
    q = b.p()
    field(q, 'TOC \\h \\z \\c "Screenshot"',
          "Update this field to list the screenshots.")

    # ── how to use ───────────────────────────────────────────────────
    b.h("How to use this document", 1, anchor="_HowToUse")
    b.p(
        "This is three books in one file. Each part is written for a different "
        "reader and can be read on its own; nobody is expected to read all of it."
    )
    b.table([
        ["Reader", "Start here", "Sections"],
        ["Managers and evaluators", "Part I — Platform Overview", "1–8"],
        ["Everyday users", "Part II — User and Administration Guide", "9, 11–14, 17"],
        ["Administrators", "Part II — security and administration", "9–10, 15–17"],
        ["Developers and integrators", "Part III — Technical Reference", "13, 18–24"],
    ], widths=[1.8, 3.0, 1.7])

    b.h("What each part is for", 2)
    b.table([
        ["Part", "Contains", "Does not contain"],
        ["I — Platform Overview",
         "What the platform is, how it is built, what it secures and what it "
         "does. Concise and visual.",
         "Installation commands, step-by-step procedures, endpoint tables"],
        ["II — User and Administration Guide",
         "Installing, signing in, every security procedure, each interface, "
         "each system, administration and troubleshooting.",
         "The complete endpoint listings"],
        ["III — Technical Reference",
         "Every address the running server publishes, with its methods, grouped "
         "by system.",
         "Explanation — read section 13 first"],
        ["IV — Supporting Information",
         "Glossary, indexes, licence, where to find the source.", "—"],
    ], widths=[1.7, 2.8, 2.0])

    b.h("Finding your way around", 2)
    b.table([
        ["Aid", "Where"],
        ["Contents, with page numbers", "Before this page"],
        ["List of figures", "After the contents"],
        ["List of screenshots", "After the figures"],
        ["Running header", "Top of every page — the part on the left, the "
                           "current section on the right"],
        ["Back to contents", "Under every section heading"],
        ["Section numbers", "Continuous 1–29 across all four parts, so 10.4 or "
                            "14.5 is unambiguous"],
        ["Glossary", "Section 25"],
    ], widths=[1.9, 4.6])
    b.note(
        "Numbering runs continuously through the whole document rather than "
        "restarting in each part, so a reference never needs the part number to "
        "be unambiguous. Sections 1–8 are Part I, 9–17 Part II, 18–24 Part III "
        "and 25–29 Part IV.")


# ══════════════════════════════════════════════════════════════════════
# Part I — Platform Overview (sections 1-8)
# ══════════════════════════════════════════════════════════════════════
def part_one(b: Book, rp: Replayer):
    b.divider(*PARTS[0][:1], PARTS[0][1], PARTS[0][2], PARTS[0][3],
              PARTS[0][4], [
                  "1  What the program does",
                  "2  How it works",
                  "3  User accounts",
                  "4  Security",
                  "5  Additional capabilities",
                  "6  The five systems",
                  "7  Platform usage overview",
                  "8  Current limitations and status",
              ]) if False else b.divider(
        "I", PARTS[0][1], PARTS[0][2], PARTS[0][3], PARTS[0][4], [
            "1  What the program does",
            "2  How it works",
            "3  User accounts",
            "4  Security",
            "5  Additional capabilities",
            "6  The five systems",
            "7  Platform usage overview",
            "8  Current limitations and status",
        ])

    # 1 ─────────────────────────────────────────────────────────────
    b.h("1  What the program does", 1)
    b.figure("fig-platform",
             "One installation carries five systems and three interfaces. "
             "Everything in this document sits behind one of the five boxes on "
             "the third row.")
    lo, hi = rp.span("1. What the program does", "2. How it works")
    rp.emit(lo + 1, hi, 1)
    b.figure("fig-composition",
             "The five systems are not the same size. The University is "
             "two-thirds of the platform's code on its own.")

    # 2 ─────────────────────────────────────────────────────────────
    b.h("2  How it works", 1)
    lo, hi = rp.span("2. How it works", "3. User accounts")
    rp.emit(lo + 1, hi, 2)
    b.figure("fig-layers",
             "Why the three interfaces agree with each other. Each is a "
             "different top layer over the same rules.")

    # 3 ─────────────────────────────────────────────────────────────
    b.h("3  User accounts", 1)
    lo, hi = rp.span("3. User accounts", "4. Security")
    rp.emit(lo + 1, hi, 3)
    b.figure("fig-identity",
             "One identity, a separate role in each system. An account with a "
             "role in more than one system can switch between them without "
             "signing in again.")

    # 4 ─────────────────────────────────────────────────────────────
    b.h("4  Security", 1)
    b.note("This section says what is protected and how. The procedures for "
           "doing any of it are in section 10.", lead="Where the detail is")
    lo, hi = rp.span("4. Security", "5. Other things worth knowing")
    rp.emit(lo + 1, hi, 4)

    # 5 ─────────────────────────────────────────────────────────────
    b.h("5  Additional capabilities", 1)
    lo, hi = rp.span("5. Other things worth knowing", "6. The five systems in detail")
    # the overview's §5 carries installation and backup material that now
    # belongs in Part II — stop before it
    stop = rp.find("Quality and testing")
    # the first H2 repeats the section title now that §5 has been retitled
    rp.emit(lo + 1, stop, 5, drop_headings={"Additional capabilities"})

    # 6 ─────────────────────────────────────────────────────────────
    b.h("6  The five systems", 1)
    b.note("Each system's menus, worked tasks and endpoints are in sections "
           "14 and 19–23. This section is the shape of each one, not how to "
           "drive it.", lead="Where the detail is")
    lo, hi = rp.span("6. The five systems in detail",
                     "7. Using the platform, step by step")
    split = rp.find("Nursery / Early Years")
    sub = rp.emit(lo + 1, split, 6)                      # switcher + API docs
    rp.emit(split, hi, 6, skip_interface=True,           # per-system prose only
            drop_shots=True, sub=sub)
    b.figure("fig-cli-vs-gui",
             "Four systems at parity, one that has diverged. In the University "
             "the desktop application reaches roughly five times as much as the "
             "command line.")

    # 7 ─────────────────────────────────────────────────────────────
    b.h("7  Platform usage overview", 1)
    b.p(
        "The platform is used through three interfaces, chosen when it is "
        "launched. They are not three views of one screen layout: each is "
        "written separately against the same rules, so the wording and the "
        "level of detail differ while the rules being applied underneath do not."
    )
    b.table([
        ["Interface", "Best suited to", "Covered in"],
        ["Desktop application",
         "Day-to-day work by teaching and support staff. The fullest interface "
         "in every system.", "Section 11"],
        ["Command line",
         "Administration on a server, batch and seasonal work, and any machine "
         "with no graphical environment.", "Section 12"],
        ["REST API",
         "Integration with other software. One server carries all five systems.",
         "Sections 13 and 18–24"],
        ["Web portal",
         "Lightweight browser access. Deepest in the University, thinner "
         "elsewhere.", "Section 11"],
    ], widths=[1.5, 3.6, 1.4])
    b.p(
        "A single launcher asks which system and which interface to open, then "
        "signs the user in once. An account that holds a role in more than one "
        "system can move between them without signing in again, and can switch "
        "between the desktop application and the command line the same way."
    )
    b.figure("fig-api-surface",
             "The published API surface. Primary is the largest, not the "
             "University — about half the University's route modules are not "
             "registered on the server.")
    b.p(
        "How much of a system each interface reaches differs, and it differs "
        "most in the University. Section 7 of Part II covers this in the detail "
        "an evaluator needs; the short version is that the desktop application "
        "is the safe default for staff, the command line is the safe default "
        "for a server, and the API should be scoped against the documentation "
        "page rather than against any description of it."
    )
    b.note("Full step-by-step instructions for all three interfaces, on all "
           "five systems, are in sections 11 to 14.", lead="Where the detail is")

    # 8 ─────────────────────────────────────────────────────────────
    b.h("8  Current limitations and status", 1)
    lo = rp.find("8. Current limitations and status")
    hi = rp.find("About this guide")
    rp.emit(lo + 1, hi, 8)


# ══════════════════════════════════════════════════════════════════════
# Part II — User and Administration Guide (sections 9-17)
# ══════════════════════════════════════════════════════════════════════
def part_two(b: Book, rp: Replayer):
    b.divider("II", PARTS[1][1], PARTS[1][2], PARTS[1][3], PARTS[1][4], [
        "9   Getting started",
        "10  Security administration",
        "11  Using the desktop application",
        "12  Using the command line",
        "13  Using the REST API",
        "14  Working with the five systems",
        "15  Everyday administration",
        "16  Moving learners between phases",
        "17  Troubleshooting",
    ])

    # 9 ─────────────────────────────────────────────────────────────
    b.h("9  Getting started", 1)
    lo, hi = rp.span("Part 1 — Getting started", "Part 2 — Security, step by step")
    rp.emit(lo + 1, hi, 9, figure_after={
        "Signing in": ("fig-signin",
                       "Signing in. The lockout path on the left is the one "
                       "worth knowing: five failures lock the account, not the "
                       "terminal."),
    })

    # 10 ────────────────────────────────────────────────────────────
    b.h("10  Security administration", 1)
    b.p(
        "This section gives the procedures. What each control does, and why it "
        "is there, is in section 4."
    )
    lo, hi = rp.span("Part 2 — Security, step by step",
                     "Part 3 — Using the interfaces")
    rp.emit(lo + 1, hi, 10, figure_after={
        "API security": (
            "fig-token",
            "The token lifecycle. Sign in once, send the access token with "
            "every request, refresh it rather than signing in again."),
    })

    # 11 ────────────────────────────────────────────────────────────
    b.h("11  Using the desktop application", 1)
    lo = rp.find("3.1 The desktop application")
    hi = rp.find("3.2 The command line")
    rp.emit(lo + 1, hi, 11, heading_shift=1)

    # 12 ────────────────────────────────────────────────────────────
    b.h("12  Using the command line", 1)
    lo = rp.find("3.2 The command line")
    hi = rp.find("3.3 The REST API")
    rp.emit(lo + 1, hi, 12, heading_shift=1)
    b.note("How much of each system the command line reaches, set against the "
           "desktop application, is charted in section 6.", lead="See also")

    # 13 ────────────────────────────────────────────────────────────
    b.h("13  Using the REST API", 1)
    lo = rp.find("3.3 The REST API")
    hi = rp.find("Part 4 — The five systems")
    rp.emit(lo + 1, hi, 13, heading_shift=1)
    b.note("Every published address, system by system, is in Part III — "
           "sections 19 to 24. Read 18 first for the conventions they all "
           "follow.", lead="Where the detail is")

    # 14 ────────────────────────────────────────────────────────────
    b.h("14  Working with the five systems", 1)
    b.p(
        "One subsection per system: what it covers, its complete menu "
        "reference, and a worked task. Endpoint listings are in Part III."
    )
    lo, hi = rp.span("Part 4 — The five systems", "Part 5 — Administration")
    rp.emit(lo + 1, hi, 14, figure_after={
        "Nursery / Early Years": ("fig-menu-nursery",
            "Nursery / Early Years — entries per menu category."),
        "Primary School": ("fig-menu-primary",
            "Primary School — entries per menu category."),
        "Secondary School": ("fig-menu-secondary",
            "Secondary School — entries per menu category."),
        "Sixth Form College": ("fig-menu-sixth_form",
            "Sixth Form College — entries per menu category."),
        "University": ("fig-university-domains",
            "Where the University's desktop features sit. Academics, operations "
            "and pastoral carry most of the system."),
    })

    # 15 ────────────────────────────────────────────────────────────
    b.h("15  Everyday administration", 1)
    lo, hi = rp.span("Part 5 — Administration",
                     "Part 6 — Moving learners between phases")
    rp.emit(lo + 1, hi, 15)

    # 16 ────────────────────────────────────────────────────────────
    b.h("16  Moving learners between phases", 1)
    lo, hi = rp.span("Part 6 — Moving learners between phases",
                     "Part 7 — Troubleshooting")
    b.figure("fig-progression",
             "A transfer goes onto a durable queue and is drained into the "
             "receiving system by a background worker, so an interrupted "
             "transfer is completed rather than lost.")
    rp.emit(lo + 1, hi, 16)

    # 17 ────────────────────────────────────────────────────────────
    b.h("17  Troubleshooting", 1)
    lo = rp.find("Part 7 — Troubleshooting")
    hi = rp.find("Appendix A — Complete endpoint reference")
    rp.emit(lo + 1, hi, 17)


# ══════════════════════════════════════════════════════════════════════
# Part III — Technical Reference (sections 18-24)
# ══════════════════════════════════════════════════════════════════════
def part_three(b: Book, inv):
    api = inv["api"]
    b.divider("III", PARTS[2][1], PARTS[2][2], PARTS[2][3], PARTS[2][4], [
        "18  API conventions",
        "19  Nursery endpoint reference",
        "20  Primary endpoint reference",
        "21  Secondary endpoint reference",
        "22  Sixth Form endpoint reference",
        "23  University endpoint reference",
        "24  Shared platform endpoints",
    ])

    # 18 ────────────────────────────────────────────────────────────
    b.h("18  API conventions", 1)
    b.p(
        "Everything in sections 19 to 24 was generated from the running "
        "server's own routing table. If an address is not listed there, this "
        "installation does not publish it — which is not the same as the "
        "feature not existing, and matters most in the University, where "
        "roughly half the route modules present in the source tree are not "
        "registered on the server."
    )
    b.h("18.1 Reading the tables", 2)
    b.table([
        ["Column", "Meaning"],
        ["Address", "The full path, including the /api/v1/ prefix and the "
                    "system segment. Segments in angle brackets are parameters "
                    "you supply"],
        ["Methods", "The HTTP methods that address accepts. HEAD and OPTIONS "
                    "are omitted throughout"],
    ], widths=[1.3, 5.2])
    b.p(
        "Addresses are grouped by endpoint group — the first path segment after "
        "the system — and groups are listed alphabetically. An address that "
        "accepts both a read and a write appears once, with both methods."
    )

    b.h("18.2 Authentication", 2)
    b.p(
        "Every address in sections 19 to 23 requires a bearer token. Obtain one "
        "from /api/v1/auth/login, send it as an Authorization header, and "
        "refresh it rather than signing in repeatedly. Section 13 covers the "
        "sequence, including the multi-factor challenge."
    )
    b.code("Authorization: Bearer <access token>")
    b.p(
        "A token reaches only the systems and roles its account holds. "
        "Authenticating does not open all five systems, and a 401 or 403 on a "
        "documented address usually means the account lacks a role in that "
        "system rather than that the address is wrong."
    )
    b.note("The full sequence, including the multi-factor challenge, is "
           "charted in section 10.", lead="See also")

    b.h("18.3 Starting the server", 2)
    b.p(
        "One process serves all five systems. Three environment variables must "
        "be set or it refuses to start — each default it declines to invent "
        "would be a real weakness."
    )
    b.code("export API_SECRET_KEY='<long random string>'")
    b.code("export JWT_SECRET_KEY='<a different long random string>'")
    b.code("export API_CORS_ORIGINS='https://app.example.com'")
    b.code("python run.py --university --api")
    b.p()
    b.table([
        ["Address", "Purpose"],
        ["/api/v1/docs", "Browsable reference generated from the running "
                         "server — the authority if this document disagrees"],
        ["/api/v1/health", "Service and database health, for monitoring"],
        ["/api/v1/health/ready", "Readiness probe"],
        ["/api/v1/health/live", "Liveness probe"],
    ], widths=[2.0, 4.5])

    b.h("18.4 The published surface", 2)
    rows = [["System", "Base address", "Groups", "Addresses", "Operations",
             "Section"]]
    for i, (key, label, prefix) in enumerate(SYSTEMS):
        s = api["summary"].get(prefix, {})
        rows.append([label, f"/api/v1/{prefix}/", str(s.get("groups", 0)),
                     str(s.get("paths", 0)), str(s.get("operations", 0)),
                     str(19 + i)])
    b.table(rows, widths=[1.5, 1.4, 0.7, 0.9, 1.0, 0.7])
    b.note("The same figures are charted in section 7.", lead="See also")

    # 19-23 ─────────────────────────────────────────────────────────
    for i, (key, label, prefix) in enumerate(SYSTEMS):
        num = 19 + i
        groups = api["systems"].get(prefix, {})
        s = api["summary"].get(prefix, {})
        b.h(f"{num}  {label} endpoint reference", 1)

        # summary page
        b.h(f"{num}.1 Summary", 2)
        b.table([
            ["Property", "Value"],
            ["Base address", f"/api/v1/{prefix}/"],
            ["Authentication", "Bearer token from /api/v1/auth/login; the "
                               "account must hold a role in this system"],
            ["Endpoint groups", str(s.get("groups", 0))],
            ["Addresses", str(s.get("paths", 0))],
            ["Operations", str(s.get("operations", 0))],
            ["Launch command", f"python run.py --{'sixthform' if key == 'sixth_form' else key.replace('_', '')} --api"],
        ], widths=[1.6, 4.9])
        if key == "secondary":
            b.note("The address uses “school” rather than “secondary” for "
                   "historical reasons. The launch flag is --secondary.")
        if key == "university":
            b.note("Around 115 route modules exist in the source tree and 60 "
                   "are registered on the server, so this API reaches "
                   "considerably less of the University than the desktop "
                   "application does. Check /api/v1/docs before scoping an "
                   "integration.")

        b.h(f"{num}.2 Functional groups", 2)
        names = sorted(groups)
        b.p(f"{len(names)} groups. Each is listed in full in {num}.3.")
        rows = [["Group", "Addresses", "Group", "Addresses"]]
        half = (len(names) + 1) // 2
        for a, bb in zip(names[:half], names[half:] + [None] * half):
            row = [f"/{a}", str(len({r['path'] for r in groups[a]}))]
            if bb:
                row += [f"/{bb}", str(len({r['path'] for r in groups[bb]}))]
            else:
                row += ["", ""]
            rows.append(row)
        b.table(rows, small=True, widths=[2.0, 1.0, 2.0, 1.0])

        b.h(f"{num}.3 Complete address listing", 2)
        for group in names:
            b.h(f"/{group}", 4)
            b.table([["Address", "Methods"]] + merge(groups[group]),
                    small=True, widths=[5.0, 1.5])

    # 24 ────────────────────────────────────────────────────────────
    b.h("24  Shared platform endpoints", 1)
    b.h("24.1 Summary", 2)
    shared = api["shared"]
    total_paths = len({r["path"] for g in shared.values() for r in g})
    total_ops = sum(len(r["methods"]) for g in shared.values() for r in g)
    b.table([
        ["Property", "Value"],
        ["Base address", "/api/v1/"],
        ["Authentication", "Mixed — the authentication group is how a token is "
                           "obtained; health is open; the rest require a token"],
        ["Endpoint groups", str(len(shared))],
        ["Addresses", str(total_paths)],
        ["Operations", str(total_ops)],
    ], widths=[1.6, 4.9])
    b.p(
        "These are not specific to one system. The authentication group is the "
        "important one: a token obtained there is what every address in "
        "sections 19 to 23 requires."
    )
    b.h("24.2 Complete address listing", 2)
    for group in sorted(shared):
        rows = merge(shared[group])
        if not rows:
            continue
        b.h(f"/{group}", 4)
        b.table([["Address", "Methods"]] + rows, small=True,
                widths=[5.0, 1.5])


METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


def merge(records):
    out = {}
    for r in records:
        out.setdefault(r["path"], set()).update(r["methods"])
    return [[path, ", ".join(sorted(ms, key=lambda m: (METHOD_ORDER.get(m, 9), m)))]
            for path, ms in sorted(out.items())]


# ══════════════════════════════════════════════════════════════════════
# Part IV — Supporting Information (sections 25-29)
# ══════════════════════════════════════════════════════════════════════
def part_four(b: Book, rp: Replayer):
    b.divider("IV", PARTS[3][1], PARTS[3][2], PARTS[3][3], PARTS[3][4], [
        "25  Glossary",
        "26  Screenshot index",
        "27  Figure index",
        "28  Licence",
        "29  Source code and further reading",
    ])

    # 25 ── merged glossary ─────────────────────────────────────────
    b.h("25  Glossary", 1)
    b.p(
        "The two glossaries the source documents carried have been merged into "
        "this one. Terms are listed once, alphabetically."
    )
    terms = {}
    for text in ("Appendix C — Glossary", "Glossary"):
        try:
            i = rp.find(text)
        except KeyError:
            continue
        for blk in rp.blocks[i:i + 6]:
            if blk["kind"] == "table":
                for row in blk["rows"][1:]:
                    if len(row) >= 2 and row[0] and row[0] != "Term":
                        terms.setdefault(row[0], row[1])
                break
    rows = [["Term", "Meaning"]] + [[k, terms[k]] for k in
                                    sorted(terms, key=str.lower)]
    b.table(rows, widths=[1.4, 5.1])
    b.note(f"{len(terms)} terms, combined from both source documents.")

    # 26 ────────────────────────────────────────────────────────────
    b.h("26  Screenshot index", 1)
    b.p(
        "Every screenshot slot in this document, in order, with the page it "
        "appears on. This is a Word field — update it (Ctrl+A, F9) to populate "
        "it."
    )
    q = b.p()
    field(q, 'TOC \\h \\z \\c "Screenshot"',
          "Update this field to list the screenshots.")
    b.h("26.1 Capturing them efficiently", 2)
    b.p(
        "Work by interface, not by system: run all five command lines in one "
        "sitting, then all five desktop applications, then work down "
        "/api/v1/docs once with the API server running. Doing it "
        "system-by-system means starting and stopping the application dozens of "
        "times."
    )
    b.table([
        ["Rule", "Why"],
        ["Demonstration data only", "This platform holds records about "
                                    "children. A screenshot is a disclosure of "
                                    "personal data, and it travels further than "
                                    "a database export"],
        ["Check the edges", "A notification, taskbar, window title or "
                            "recent-files list can leak a real name into an "
                            "otherwise clean image"],
        ["Redact by flattening", "A shape placed over an image in Word can be "
                                 "dragged aside by the next person to open it"],
        ["Never capture a token", "A token is a working credential for as long "
                                  "as it lives"],
        ["Capture the window, not the screen", "And keep the window size "
                                               "consistent so images sit at one "
                                               "scale"],
        ["Save as PNG", "Interface text compresses badly as JPEG"],
    ], widths=[1.9, 4.6])

    # 27 ────────────────────────────────────────────────────────────
    b.h("27  Figure index", 1)
    b.p(
        "The charts and diagrams in this document. All are generated from the "
        "same inventory as the reference tables, so they cannot disagree with "
        "them."
    )
    q = b.p()
    field(q, 'TOC \\h \\z \\c "Figure"',
          "Update this field to list the figures.")

    # 28 ────────────────────────────────────────────────────────────
    b.h("28  Licence", 1)
    try:
        i = rp.find("Licence")
        for blk in rp.blocks[i + 1:i + 4]:
            if blk["kind"] == "para":
                b.p(blk["text"])
                break
    except KeyError:
        b.p("The platform is released under the MIT Licence.")

    # 29 ────────────────────────────────────────────────────────────
    b.h("29  Source code and further reading", 1)
    try:
        i = rp.find("Source code and further reading")
        for blk in rp.blocks[i + 1:i + 8]:
            if blk["kind"] in ("para", "code"):
                (b.code if blk["kind"] == "code" else b.p)(blk["text"])
    except KeyError:
        pass
    b.h("29.1 Rebuilding this document", 2)
    b.p(
        "Part III and the menu listings in section 14 are generated. To rebuild "
        "them after the software changes:"
    )
    for line in [
        "python tools/docs/extract_inventory.py inventory.json",
        "python tools/docs/build_figures.py inventory.json "
        "docs/assets/guide/",
        "python tools/docs/build_combined.py overview.json "
        "inventory.json out.docx",
    ]:
        b.code(line)
    b.p()
    b.note(
        "After rebuilding, open the file in Word, select all and press F9 to "
        "populate the contents list, the figure and screenshot lists and the "
        "page numbers. They are fields, and a freshly built file shows them "
        "empty until they are updated.")


# ══════════════════════════════════════════════════════════════════════
def main(overview_json, inventory_json, out_path, figdir=None):
    blocks = json.loads(Path(overview_json).read_text())
    inv = json.loads(Path(inventory_json).read_text())
    figdir = figdir or str(Path(out_path).parent / "assets" / "guide")

    b = Book(figdir)
    rp = Replayer(b, blocks)

    front_matter(b)
    part_one(b, rp)
    part_two(b, rp)
    part_three(b, inv)
    part_four(b, rp)

    b.doc.save(out_path)
    print("saved", out_path)
    print("screenshots:", len(b.shots), " figures:", len(b.figs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         sys.argv[4] if len(sys.argv) > 4 else None)
