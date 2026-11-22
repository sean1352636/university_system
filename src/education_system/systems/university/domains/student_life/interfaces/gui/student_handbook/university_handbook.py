"""
Student Handbook 2026/27 (named after the institution set in admin Branding)
A book-style Tkinter application with a clickable contents page,
page-turning, a ribbon bookmark, and in-text hyperlinks.

Opened from the admin, staff and student portals ("Student Handbook"),
via :func:`open_student_handbook`. Standalone:
  python -m education_system.systems.university.domains.student_life.interfaces.gui.student_handbook.university_handbook
Needs only the Python standard library (Tkinter).

Controls
  Left / Right arrows, Page Up / Page Down ... turn pages
  Home ....................................... back to the contents
  Click any underlined link .................. jump to that section
  Sidebar tabs ............................... jump to a chapter
  B .......................................... bookmark / return to bookmark
"""

import tkinter as tk
from tkinter import font as tkfont

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
DESK = "#3b2a1e"          # wooden desk behind the book
COVER = "#5a1e1e"         # oxblood leather cover
COVER_EDGE = "#3d1212"
GOLD = "#c9a24a"
PAPER = "#f6efdf"         # page colour
PAPER_SHADE = "#e9dfc8"   # shadow near the spine
PAGE_EDGE = "#d8ccb1"     # stacked page edges
INK = "#2b2118"
INK_SOFT = "#6b5a48"
LINK = "#7a2a1a"
LINK_HOVER = "#b5452c"
RULE = "#b9a882"

from education_system.systems.university.domains.student_life.domain.student_handbook.content import (
    handbook,
    MOTTO,
    SUBTITLE,
    institution_address,
    institution_name,
    short_name,
    YEAR,
)


# --------------------------------------------------------------------------
# Book model: flatten content into an ordered list of pages
# --------------------------------------------------------------------------
class Book:
    LINES_PER_PAGE = 22   # rough page capacity for pagination
    CHARS_PER_LINE = 58

    def __init__(self, chapters):
        self.chapters = chapters
        self.pages = []          # list of dicts
        self.anchor = {}         # section/chapter id -> page index
        self._build()

    def _lines_needed(self, text):
        if text.startswith("•"):
            return 1.3
        return max(1, -(-len(text) // self.CHARS_PER_LINE)) + 1  # +1 for paragraph gap

    def _build(self):
        self.pages.append({"kind": "cover"})
        self.anchor["cover"] = 0
        half = (len(self.chapters) + 1) // 2
        self.pages.append({"kind": "toc", "chapters": list(enumerate(self.chapters[:half], 1))})
        self.pages.append({"kind": "toc", "chapters": list(enumerate(self.chapters[half:], half + 1)),
                           "cont": True})
        self.anchor["toc"] = 1

        for c_num, ch in enumerate(self.chapters, start=1):
            self.anchor[ch["id"]] = len(self.pages)
            self.pages.append({"kind": "chapter", "num": c_num, "chapter": ch})
            for s_num, sec in enumerate(ch["sections"], start=1):
                self.anchor[sec["id"]] = len(self.pages)
                chunk, used = [], 4   # heading takes room
                cont = False
                for para in sec["body"]:
                    need = self._lines_needed(para)
                    if chunk and used + need > self.LINES_PER_PAGE:
                        self.pages.append(self._section_page(c_num, s_num, ch, sec, chunk, cont))
                        chunk, used, cont = [], 2, True
                    chunk.append(para)
                    used += need
                self.pages.append(self._section_page(c_num, s_num, ch, sec, chunk, cont))

        self.anchor["end"] = len(self.pages)
        self.pages.append({"kind": "end"})

    @staticmethod
    def _section_page(c_num, s_num, ch, sec, paras, cont):
        return {"kind": "section", "num": f"{c_num}.{s_num}", "chapter": ch,
                "section": sec, "paras": paras, "continued": cont}

    def page_number(self, idx):
        """Printed page number (cover and contents are unnumbered)."""
        return idx - 2 if idx >= 3 else None

    def chapter_of(self, idx):
        page = self.pages[idx]
        return page.get("chapter", {}).get("id")


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class HandbookApp(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.institution = institution_name()
        self.title(f"{self.institution} — {SUBTITLE} {YEAR}")
        self.configure(bg=DESK)
        self.geometry("1400x900")
        self.minsize(1200, 800)

        self.chapters = handbook()
        self.book = Book(self.chapters)
        self.spread = 0           # index of left-hand page of the current spread
        self.bookmark = None
        self.history = []

        self._fonts()
        self._layout()
        self._bindings()
        self.after(50, lambda: self.go_to(0, record=False))

    # ----- fonts ---------------------------------------------------------
    def _fonts(self):
        families = set(tkfont.families(root=self))
        serif = next((f for f in ("Georgia", "Palatino Linotype", "Book Antiqua", "Cambria",
                                  "Times New Roman", "DejaVu Serif", "Liberation Serif")
                      if f in families), "Times")
        mono = next((f for f in ("Consolas", "Courier New", "DejaVu Sans Mono", "Liberation Mono")
                     if f in families), "Courier")
        self.f_body = tkfont.Font(root=self, family=serif, size=12)
        self.f_body_mono = tkfont.Font(root=self, family=mono, size=11)
        self.f_h1 = tkfont.Font(root=self, family=serif, size=26, weight="bold")
        self.f_h2 = tkfont.Font(root=self, family=serif, size=17, weight="bold")
        self.f_small = tkfont.Font(root=self, family=serif, size=10, slant="italic")
        self.f_caps = tkfont.Font(root=self, family=serif, size=10)
        self.f_dropcap = tkfont.Font(root=self, family=serif, size=19, weight="bold")
        self.f_cover_t = tkfont.Font(root=self, family=serif, size=34, weight="bold")
        self.f_cover_m = tkfont.Font(root=self, family=serif, size=28, weight="bold")
        self.f_cover_s = tkfont.Font(root=self, family=serif, size=20, slant="italic")
        self.f_tab = tkfont.Font(root=self, family=serif, size=10, weight="bold")
        self.f_toc = tkfont.Font(root=self, family=serif, size=12)
        self.f_toc_ch = tkfont.Font(root=self, family=serif, size=13, weight="bold")
        self.f_link = tkfont.Font(root=self, family=serif, size=12, underline=True)
        self.f_btn = tkfont.Font(root=self, family=serif, size=11)

    # ----- window layout -------------------------------------------------
    def _layout(self):
        # top toolbar
        bar = tk.Frame(self, bg=DESK)
        bar.pack(side="top", fill="x", padx=20, pady=(12, 0))

        def btn(text, cmd):
            b = tk.Label(bar, text=text, font=self.f_btn, fg=GOLD, bg=DESK, padx=10, pady=4,
                         cursor="hand2")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(fg="#f1d99a"))
            b.bind("<Leave>", lambda e: b.config(fg=GOLD))
            b.pack(side="left")
            return b

        btn("☰  Contents", lambda: self.go_to(self.book.anchor["toc"]))
        btn("⟲  Back", self.back)
        self.bm_btn = btn("🔖  Bookmark", self.toggle_bookmark)
        tk.Label(bar, text=f"{self.institution}  ·  {SUBTITLE}  ·  {YEAR}", font=self.f_small,
                 fg="#a88f6a", bg=DESK).pack(side="right")

        # main area: book + chapter tabs
        main = tk.Frame(self, bg=DESK)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        self.canvas = tk.Canvas(main, bg=DESK, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.tabs = tk.Frame(main, bg=DESK)
        self.tabs.pack(side="right", fill="y", pady=40)
        self.tab_widgets = {}
        tab_colours = ["#7d3b2a", "#2f5d50", "#3b4f7d", "#7d6a2f", "#5b3b7d", "#4a4a4a"]
        for i, ch in enumerate(self.chapters):
            t = tk.Label(self.tabs, text=f" {i + 1}  {ch['title']} ", font=self.f_tab,
                         fg="#f8f1e0", bg=tab_colours[i % len(tab_colours)], anchor="w",
                         padx=8, pady=9, cursor="hand2", width=20)
            t.pack(fill="x", pady=3)
            t.bind("<Button-1>", lambda e, cid=ch["id"]: self.go_to(self.book.anchor[cid]))
            self.tab_widgets[ch["id"]] = t

        # bottom navigation
        nav = tk.Frame(self, bg=DESK)
        nav.pack(side="bottom", fill="x", padx=20, pady=(0, 14))
        self.prev_lbl = tk.Label(nav, text="◀  Previous", font=self.f_btn, fg=GOLD, bg=DESK,
                                 cursor="hand2")
        self.prev_lbl.pack(side="left")
        self.prev_lbl.bind("<Button-1>", lambda e: self.turn(-1))
        self.next_lbl = tk.Label(nav, text="Next  ▶", font=self.f_btn, fg=GOLD, bg=DESK,
                                 cursor="hand2")
        self.next_lbl.pack(side="right")
        self.next_lbl.bind("<Button-1>", lambda e: self.turn(1))
        self.status = tk.Label(nav, text="", font=self.f_small, fg="#a88f6a", bg=DESK)
        self.status.pack()

        # the two pages are Text widgets placed onto the canvas
        self.left = self._make_page()
        self.right = self._make_page()

    def _make_page(self):
        t = tk.Text(self.canvas, wrap="word", bg=PAPER, fg=INK, relief="flat", bd=0,
                    highlightthickness=0, font=self.f_body, padx=8, pady=4, cursor="arrow",
                    spacing1=2, spacing3=6, insertwidth=0)
        t.tag_configure("h1", font=self.f_h1, spacing1=10, spacing3=4)
        t.tag_configure("h2", font=self.f_h2, spacing1=6, spacing3=10)
        t.tag_configure("kicker", font=self.f_caps, foreground=INK_SOFT, spacing3=2)
        t.tag_configure("center", justify="center")
        t.tag_configure("justify", justify="left", lmargin1=0, lmargin2=0)
        t.tag_configure("indent", lmargin1=24)
        t.tag_configure("bullet", lmargin1=12, lmargin2=26, font=self.f_body_mono)
        t.tag_configure("muted", foreground=INK_SOFT, font=self.f_small)
        t.tag_configure("dropcap", font=self.f_dropcap, foreground=COVER)
        t.tag_configure("toc_ch", font=self.f_toc_ch, spacing1=10, spacing3=2)
        t.tag_configure("toc", font=self.f_toc, lmargin1=26, lmargin2=26, spacing1=1, spacing3=1)
        t.tag_configure("rule", foreground=RULE, justify="center")
        t.tag_configure("dots", foreground=RULE)
        t.tag_configure("pgnum", foreground=INK_SOFT)
        t.tag_configure("big", font=self.f_cover_s, foreground=COVER, justify="center")
        return t

    def _bindings(self):
        for key in ("<Right>", "<Next>", "<space>"):
            self.bind(key, lambda e: self.turn(1))
        for key in ("<Left>", "<Prior>", "<BackSpace>"):
            self.bind(key, lambda e: self.turn(-1))
        self.bind("<Home>", lambda e: self.go_to(self.book.anchor["toc"]))
        self.bind("<KeyPress-b>", lambda e: self.toggle_bookmark())
        self.bind("<Alt-Left>", lambda e: self.back())
        self.canvas.bind("<Configure>", lambda e: self.render())

    # ----- navigation ----------------------------------------------------
    def _spread_for(self, idx):
        """Cover sits alone on the right; afterwards pages pair up (odd-left)."""
        if idx == 0:
            return 0
        return idx if idx % 2 == 1 else idx - 1

    def go_to(self, idx, record=True):
        idx = max(0, min(idx, len(self.book.pages) - 1))
        new = self._spread_for(idx)
        if record and new != self.spread:
            self.history.append(self.spread)
        self.spread = new
        self.render()

    def turn(self, direction):
        if self.spread == 0:
            target = 1 if direction > 0 else 0
        else:
            target = self.spread + 2 * direction
            if target < 1:
                target = 0
        if 0 <= target < len(self.book.pages):
            self.spread = target
            self.render()

    def back(self):
        if self.history:
            self.spread = self.history.pop()
            self.render()

    def toggle_bookmark(self):
        if self.bookmark is not None and self.bookmark != self.spread:
            self.go_to(self.bookmark)
        elif self.bookmark == self.spread:
            self.bookmark = None
        else:
            self.bookmark = self.spread
        self.render()

    # ----- drawing -------------------------------------------------------
    def render(self):
        c = self.canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 50 or H < 50:
            return

        # book geometry, keep a pleasing aspect ratio
        book_h = H - 30
        book_w = min(W - 40, int(book_h * 1.45))
        book_h = int(book_w / 1.45)
        x0 = (W - book_w) // 2
        y0 = (H - book_h) // 2
        x1, y1 = x0 + book_w, y0 + book_h
        mid = (x0 + x1) // 2

        if self.spread != 0:
            c.create_rectangle(x0 + 10, y0 + 14, x1 + 12, y1 + 16, fill="#24180f", outline="")

        if self.spread == 0:
            self._draw_cover(c, mid, x1, y0, y1)
            self.left.place_forget()
            self.right.place_forget()
        else:
            self._draw_open_book(c, x0, y0, x1, y1, mid)

        self._update_chrome()

    def _draw_cover(self, c, x0, x1, y0, y1):
        # closed book: spine on the left, cover on the right half of the area
        w = x1 - x0
        x0 -= w // 2
        x1 -= w // 2
        c.create_rectangle(x0 + 12, y0 + 14, x1 + 16, y1 + 14, fill="#24180f", outline="")
        # page block peeking out
        c.create_rectangle(x0 + 8, y0 + 6, x1 + 6, y1 - 2, fill=PAGE_EDGE, outline="")
        for i in range(0, 6, 2):
            c.create_line(x1 + i, y0 + 8, x1 + i, y1 - 4, fill="#c4b696")
        # cover
        c.create_rectangle(x0, y0, x1, y1, fill=COVER, outline=COVER_EDGE, width=3)
        c.create_rectangle(x0, y0, x0 + 28, y1, fill=COVER_EDGE, outline="")   # spine hinge
        for yy in (y0 + 40, y1 - 40):
            c.create_line(x0 + 4, yy, x0 + 24, yy, fill=GOLD, width=2)
        # gilt border
        m = 40
        c.create_rectangle(x0 + m, y0 + m, x1 - m + 20, y1 - m, outline=GOLD, width=2)
        c.create_rectangle(x0 + m + 7, y0 + m + 7, x1 - m + 13, y1 - m - 7, outline=GOLD, width=1)
        cx = (x0 + 28 + x1) // 2
        # crest
        cy = y0 + (y1 - y0) * 0.32
        r = 46
        c.create_polygon(cx - r, cy - r, cx + r, cy - r, cx + r, cy + 10, cx, cy + r + 18,
                         cx - r, cy + 10, fill="", outline=GOLD, width=3, smooth=False)
        c.create_text(cx, cy - 4, text=(short_name(self.institution)[:1] or "U").upper(),
                      font=self.f_cover_t, fill=GOLD)
        # titles
        c.create_text(cx, y0 + (y1 - y0) * 0.56, text=self.institution.upper(), font=self.f_h2,
                      fill=GOLD)
        c.create_text(cx, y0 + (y1 - y0) * 0.645, text=SUBTITLE, font=self.f_cover_m, fill=GOLD)
        c.create_line(cx - 90, y0 + (y1 - y0) * 0.71, cx + 90, y0 + (y1 - y0) * 0.71,
                      fill=GOLD, width=1)
        c.create_text(cx, y0 + (y1 - y0) * 0.76, text=YEAR, font=self.f_cover_s, fill=GOLD)
        c.create_text(cx, y1 - m - 30, text=MOTTO, font=self.f_small, fill=GOLD)
        # clickable "open" hint
        hint = c.create_text(cx, y1 - 14, text="Click the cover or press → to open",
                             font=self.f_small, fill="#d9c08a")
        cover_hit = c.create_rectangle(x0, y0, x1, y1, outline="", fill="")
        for item in (cover_hit, hint):
            c.tag_bind(item, "<Button-1>", lambda e: self.turn(1))
        c.config(cursor="hand2")

    def _draw_open_book(self, c, x0, y0, x1, y1, mid):
        c.config(cursor="")
        # leather boards behind the pages
        c.create_rectangle(x0 - 10, y0 - 8, x1 + 10, y1 + 8, fill=COVER, outline=COVER_EDGE, width=2)
        # stacked page edges, thicker on the side with more pages
        total = len(self.book.pages)
        left_stack = max(2, min(9, int(9 * self.spread / total)))
        right_stack = max(2, min(9, 9 - left_stack + 2))
        for i in range(left_stack):
            c.create_rectangle(x0 - i, y0 + i * 0.4, mid, y1 - i * 0.4 + 2,
                               fill=PAGE_EDGE if i % 2 else "#e3d8bf", outline="")
        for i in range(right_stack):
            c.create_rectangle(mid, y0 + i * 0.4, x1 + i, y1 - i * 0.4 + 2,
                               fill=PAGE_EDGE if i % 2 else "#e3d8bf", outline="")
        # the two pages
        c.create_rectangle(x0, y0, mid, y1, fill=PAPER, outline="")
        c.create_rectangle(mid, y0, x1, y1, fill=PAPER, outline="")
        # gutter shadow, a soft gradient into the spine
        steps = 26
        for i in range(steps):
            t = i / steps
            col = self._blend(PAPER_SHADE, PAPER, t)
            c.create_line(mid - (steps - i), y0, mid - (steps - i), y1, fill=col)
            c.create_line(mid + (steps - i), y0, mid + (steps - i), y1, fill=col)
        c.create_line(mid, y0, mid, y1, fill="#bfae8c", width=2)

        # ribbon bookmark
        if self.bookmark == self.spread:
            rx = mid + 40
            c.create_polygon(rx, y0 - 12, rx + 18, y0 - 12, rx + 18, y0 + 90, rx + 9, y0 + 78,
                             rx, y0 + 90, fill="#9c1f2e", outline="#6f1520")

        # place text widgets on each page
        pad_x, pad_top, pad_bot = 46, 52, 54
        pw = (mid - x0) - pad_x * 2
        self.page_w = pw
        ph = (y1 - y0) - pad_top - pad_bot
        self.left.place(x=x0 + pad_x, y=y0 + pad_top, width=pw, height=ph)
        self.right.place(x=mid + pad_x, y=y0 + pad_top, width=pw, height=ph)

        li, ri = self.spread, self.spread + 1
        self._fill_page(self.left, li)
        if ri < len(self.book.pages):
            self._fill_page(self.right, ri)
        else:
            self._clear(self.right)

        # running heads and folios
        for idx, (px0, px1, align) in ((li, (x0, mid, "w")), (ri, (mid, x1, "e"))):
            if idx >= len(self.book.pages):
                continue
            page = self.book.pages[idx]
            head = self._running_head(page, left=(align == "w"))
            if head:
                hx = px0 + pad_x if align == "w" else px1 - pad_x
                c.create_text(hx, y0 + 26, text=head, font=self.f_small, fill=INK_SOFT, anchor=align)
                c.create_line(px0 + pad_x, y0 + 40, px1 - pad_x, y0 + 40, fill=RULE)
            num = self.book.page_number(idx)
            if num and page["kind"] != "chapter":
                fx = px0 + pad_x if align == "w" else px1 - pad_x
                c.create_text(fx, y1 - 26, text=str(num), font=self.f_caps, fill=INK_SOFT,
                              anchor=align)

        # page-corner turn hotspots
        self._corner(c, x0, y1, -1)
        self._corner(c, x1, y1, 1)

    def _corner(self, c, x, y, direction):
        s = 34
        if direction > 0:
            pts = (x - s, y, x, y, x, y - s)
            shade = (x - s, y, x - s + 4, y - s + 4, x, y - s)
        else:
            pts = (x + s, y, x, y, x, y - s)
            shade = (x + s, y, x + s - 4, y - s + 4, x, y - s)
        can_turn = (direction < 0) or (self.spread + 2 < len(self.book.pages))
        if not can_turn:
            return
        a = c.create_polygon(*pts, fill="#e4d7b9", outline="#c8b893")
        b = c.create_polygon(*shade, fill="#d6c7a3", outline="")
        for item in (a, b):
            c.tag_bind(item, "<Button-1>", lambda e: self.turn(direction))
            c.tag_bind(item, "<Enter>", lambda e: c.config(cursor="hand2"))
            c.tag_bind(item, "<Leave>", lambda e: c.config(cursor=""))

    @staticmethod
    def _blend(c1, c2, t):
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))

    def _running_head(self, page, left):
        if page["kind"] == "section":
            return page["chapter"]["title"] if left else page["section"]["title"]
        if page["kind"] == "toc":
            return SUBTITLE
        return ""

    # ----- page content --------------------------------------------------
    def _clear(self, t):
        t.config(state="normal")
        t.delete("1.0", "end")
        for tag in t.tag_names():
            if tag.startswith("lnk_"):
                t.tag_delete(tag)
        t.config(state="disabled")

    def _fill_page(self, t, idx):
        self._clear(t)
        t.config(state="normal")
        page = self.book.pages[idx]
        kind = page["kind"]
        if kind == "toc":
            self._page_toc(t, page)
        elif kind == "chapter":
            self._page_chapter(t, page)
        elif kind == "section":
            self._page_section(t, page)
        elif kind == "end":
            self._page_end(t)
        t.config(state="disabled")

    def _link(self, t, label, target, tags=()):
        """Insert clickable text that jumps to an anchor id."""
        tag = f"lnk_{target}_{t.index('end')}"
        t.tag_configure(tag, foreground=LINK, font=self.f_link)
        t.tag_bind(tag, "<Button-1>", lambda e: self.go_to(self.book.anchor.get(target, 1)))
        t.tag_bind(tag, "<Enter>", lambda e: (t.tag_configure(tag, foreground=LINK_HOVER),
                                              t.config(cursor="hand2")))
        t.tag_bind(tag, "<Leave>", lambda e: (t.tag_configure(tag, foreground=LINK),
                                              t.config(cursor="arrow")))
        t.insert("end", label, (tag,) + tuple(tags))

    def _rich(self, t, text, tags=()):
        """Insert text that may contain [[label|target]] links."""
        while "[[" in text:
            pre, rest = text.split("[[", 1)
            inner, text = rest.split("]]", 1)
            label, target = inner.split("|")
            t.insert("end", pre, tags)
            self._link(t, label, target, tags)
        t.insert("end", text, tags)

    def _page_toc(self, t, page):
        if page.get("cont"):
            t.insert("end", "Contents (continued)\n", ("muted",))
        else:
            t.insert("end", "Contents\n", ("h1", "center"))
            t.insert("end", "❦\n", ("rule",))
        # dot leaders measured to the real page width, page number on a right tab
        avail = getattr(self, "page_w", 400) - 16 - 26 - 4
        t.tag_configure("toc", tabs=(avail, "right"))
        dot_w = self.f_toc.measure(".")
        for c_num, ch in page["chapters"]:
            t.insert("end", f"{c_num}.  ", ("toc_ch",))
            self._link(t, ch["title"], ch["id"], ("toc_ch",))
            t.insert("end", "\n", ("toc_ch",))
            for s_num, sec in enumerate(ch["sections"], start=1):
                pg = str(self.book.page_number(self.book.anchor[sec["id"]]))
                label = f"{c_num}.{s_num}  {sec['title']}"
                gap = avail - self.f_link.measure(label) - self.f_toc.measure(pg) - 16
                dots = "." * max(2, gap // dot_w)
                self._link(t, label, sec["id"], ("toc",))
                t.insert("end", f" {dots}", ("toc", "dots"))
                t.insert("end", f"\t{pg}\n", ("toc", "pgnum"))

    def _page_chapter(self, t, page):
        ch = page["chapter"]
        t.insert("end", "\n\n\n", ())
        t.insert("end", f"CHAPTER {self._roman(page['num'])}\n", ("kicker", "center"))
        t.insert("end", "— ❦ —\n", ("rule",))
        t.insert("end", ch["title"] + "\n\n", ("h1", "center"))
        t.insert("end", "In this chapter\n", ("muted", "center"))
        for s_num, sec in enumerate(ch["sections"], start=1):
            t.insert("end", f"{page['num']}.{s_num}   ", ("center",))
            self._link(t, sec["title"], sec["id"], ("center",))
            t.insert("end", "\n", ("center",))

    def _page_section(self, t, page):
        sec = page["section"]
        if page["continued"]:
            t.insert("end", f"{sec['title']} (continued)\n", ("muted",))
        else:
            t.insert("end", f"§ {page['num']}\n", ("kicker",))
            t.insert("end", sec["title"] + "\n", ("h2",))
        first = not page["continued"]
        for para in page["paras"]:
            if para.startswith("•"):
                self._rich(t, para + "\n", ("bullet",))
                continue
            if first and len(para) > 1 and para[0].isalpha():
                t.insert("end", para[0], ("dropcap",))
                self._rich(t, para[1:] + "\n", ("justify",))
                first = False
            else:
                self._rich(t, para + "\n", ("justify", "indent"))

    def _page_end(self, t):
        t.insert("end", "\n\n\n\n\n", ())
        t.insert("end", "❦\n\n", ("rule", "big"))
        t.insert("end", "Finis\n\n", ("big",))
        t.insert("end", f"{self.institution}\n{institution_address()}\n\n", ("muted", "center"))
        t.insert("end", "Back to ", ("center",))
        self._link(t, "Contents", "toc", ("center",))
        t.insert("end", "  ·  ", ("center",))
        self._link(t, "Cover", "cover", ("center",))
        t.insert("end", "\n", ("center",))

    @staticmethod
    def _roman(n):
        vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
        out = ""
        for v, s in vals:
            while n >= v:
                out += s
                n -= v
        return out

    # ----- toolbar / tabs / status --------------------------------------
    def _update_chrome(self):
        total = len(self.book.pages)
        if self.spread == 0:
            self.status.config(text="Cover")
        else:
            nums = [self.book.page_number(i) for i in (self.spread, self.spread + 1)
                    if i < total and self.book.page_number(i)]
            label = "Contents" if self.spread == 1 else (
                "Pages " + "–".join(str(n) for n in nums) if nums else "")
            self.status.config(text=f"{label}   of {total - 3}")
        self.prev_lbl.config(fg=GOLD if self.spread > 0 else "#6b5540")
        self.next_lbl.config(fg=GOLD if self.spread + 2 < total or self.spread == 0 else "#6b5540")

        if self.bookmark is None:
            self.bm_btn.config(text="🔖  Bookmark this page")
        elif self.bookmark == self.spread:
            self.bm_btn.config(text="🔖  Remove bookmark")
        else:
            self.bm_btn.config(text="🔖  Go to bookmark")

        current = {self.book.chapter_of(i) for i in (self.spread, self.spread + 1) if i < total}
        for cid, w in self.tab_widgets.items():
            w.config(padx=16 if cid in current else 8,
                     relief="raised" if cid in current else "flat")


def open_student_handbook(master):
    """Open the handbook over ``master``, or raise the one already open."""
    existing = getattr(master, "_student_handbook", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing
    except tk.TclError:
        pass
    window = HandbookApp(master)
    master._student_handbook = window
    window.focus_set()
    return window


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = HandbookApp(root)
    app.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
