"""Unified Finance hub for the Sixth Form System.

A single window that brings together every finance domain module —
fees, bursaries, trips, receipts, expense claims, funding and the
statutory census / ILR returns — behind one sidebar-navigated shell.

The layout deliberately mirrors the University system's Finance
Management GUI: a coloured header bar, a scrollable sidebar of section
buttons, a content pane that swaps in place, and a status bar — with an
at-a-glance dashboard of headline figures on top. Each finance section
embeds the *exact* same tabs as its standalone window via the
``build_*_notebook`` helpers, so there is one source of truth per module.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.shared import branding

# Notebook builders reused from the standalone finance windows. Keeping
# the imports here (rather than lazily) is cheap — these modules are pure
# Tkinter view code with no heavy import-time side effects.
from education_system.sixthform_system.modules.domain.finance.fees import fees_views
from education_system.sixthform_system.modules.domain.finance.bursaries import bursaries_views
from education_system.sixthform_system.modules.domain.finance.trips import trips_views
from education_system.sixthform_system.modules.domain.finance.receipts import receipts_views
from education_system.sixthform_system.modules.domain.finance.expense_claims import expense_claims_views
from education_system.sixthform_system.modules.domain.finance.funding import funding_views
from education_system.sixthform_system.modules.domain.finance.census_ilr import census_ilr_views

# Data layers (used by the dashboard for headline figures).
from education_system.sixthform_system.modules.domain.finance.fees import fees as fees_data
from education_system.sixthform_system.modules.domain.finance.bursaries import bursaries as bursaries_data
from education_system.sixthform_system.modules.domain.finance.trips import trips as trips_data
from education_system.sixthform_system.modules.domain.finance.receipts import receipts as receipts_data
from education_system.sixthform_system.modules.domain.finance.expense_claims import expense_claims as expense_data
from education_system.sixthform_system.modules.domain.finance.funding import funding as funding_data
from education_system.sixthform_system.modules.domain.finance.census_ilr import census_ilr as census_data

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)
CURRENCY_SYMBOL = "£"

# University-Finance-style palette.
COLORS = {
    "primary": "#2c3e50",    # header + sidebar background
    "secondary": "#34495e",  # idle nav button
    "active": "#1abc9c",     # selected nav button
    "accent": "#3498db",
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "light": "#ecf0f1",      # window / content background
    "card": "#ffffff",
    "text": "#2c3e50",
    "muted": "#7f8c8d",
}


def _money(v) -> str:
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if v < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(v):,.2f}"


def open_finance_hub(parent=None) -> "FinanceHubGUI":
    """Entry point used by the launcher / main GUI.

    ``parent`` may be the main GUI object (with a ``.root``), a Tk widget,
    or ``None`` (standalone — creates its own root).
    """
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    return FinanceHubGUI(win)


class FinanceHubGUI:
    """The unified finance workspace window."""

    # (section_id, sidebar label, notebook builder | None for dashboard)
    SECTIONS = [
        ("dashboard", "\U0001F4CA  Dashboard", None),
        ("fees", "\U0001F4B7  Fees & Payments", fees_views.build_fees_notebook),
        ("bursaries", "\U0001F393  Bursaries", bursaries_views.build_bursaries_notebook),
        ("trips", "\U0001F68C  Trips & Payments", trips_views.build_trips_notebook),
        ("receipts", "\U0001F9FE  Receipts", receipts_views.build_receipts_notebook),
        ("expenses", "\U0001F4BC  Expense Claims", expense_claims_views.build_expense_claims_notebook),
        ("funding", "\U0001F3E6  Funding", funding_views.build_funding_notebook),
        ("census", "\U0001F4D1  Census / ILR", census_ilr_views.build_census_ilr_notebook),
    ]

    def __init__(self, win: tk.Misc) -> None:
        self.win = win
        win.title(f"Finance — {branding.SYSTEM_NAME}")
        try:
            win.geometry(WIN_GEOMETRY)
            win.minsize(*WIN_MINSIZE)
        except tk.TclError:  # headless / odd masters
            pass
        win.configure(bg=COLORS["light"])

        self._builders = {sid: b for sid, _label, b in self.SECTIONS}
        self._frames: dict[str, tk.Frame] = {}   # lazily built section frames
        self._buttons: dict[str, tk.Button] = {}
        self._current: str | None = None

        self._build_header()
        self._build_body()
        self._build_status_bar()
        self.show_section("dashboard")

    # ── Layout ──────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = tk.Frame(self.win, bg=COLORS["primary"], height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="\U0001F4B0  Finance Management",
            font=("Arial", 20, "bold"), fg="white", bg=COLORS["primary"],
        ).pack(side="left", padx=20)
        tk.Button(
            header, text="Close", command=self.win.destroy,
            font=("Arial", 10, "bold"), bg="white", fg=COLORS["primary"],
            relief="flat", padx=14, pady=4, cursor="hand2",
        ).pack(side="right", padx=20)
        tk.Button(
            header, text="↻  Refresh Dashboard",
            command=self.refresh_dashboard,
            font=("Arial", 10, "bold"), bg=COLORS["accent"], fg="white",
            relief="flat", padx=14, pady=4, cursor="hand2",
        ).pack(side="right", padx=4)

    def _build_body(self) -> None:
        body = tk.Frame(self.win, bg=COLORS["light"])
        body.pack(fill="both", expand=True)

        # Sidebar (scrollable, fixed width).
        side = tk.Frame(body, bg=COLORS["primary"], width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        canvas = tk.Canvas(side, bg=COLORS["primary"], highlightthickness=0,
                           width=240)
        sb = ttk.Scrollbar(side, orient="vertical", command=canvas.yview)
        self._nav = tk.Frame(canvas, bg=COLORS["primary"])
        self._nav.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._nav, anchor="nw", width=240)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Label(self._nav, text="SECTIONS", font=("Arial", 9, "bold"),
                 fg=COLORS["muted"], bg=COLORS["primary"], anchor="w",
                 ).pack(fill="x", padx=16, pady=(14, 6))
        for sid, label, _b in self.SECTIONS:
            btn = tk.Button(
                self._nav, text=label, anchor="w",
                command=lambda s=sid: self.show_section(s),
                font=("Arial", 11), fg="white", bg=COLORS["secondary"],
                activebackground=COLORS["active"], activeforeground="white",
                relief="flat", bd=0, padx=18, pady=11, cursor="hand2",
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._buttons[sid] = btn

        # Content pane.
        self._content = tk.Frame(body, bg=COLORS["light"])
        self._content.pack(side="left", fill="both", expand=True)

    def _build_status_bar(self) -> None:
        self._status = tk.StringVar(value="Ready")
        bar = tk.Frame(self.win, bg=COLORS["secondary"], height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Label(bar, textvariable=self._status, fg="white",
                 bg=COLORS["secondary"], font=("Arial", 9), anchor="w",
                 ).pack(side="left", padx=12)
        tk.Label(bar, text=branding.SYSTEM_NAME, fg=COLORS["light"],
                 bg=COLORS["secondary"], font=("Arial", 9), anchor="e",
                 ).pack(side="right", padx=12)

    # ── Navigation ──────────────────────────────────────────────────

    def show_section(self, section_id: str) -> None:
        if section_id not in self._frames:
            self._frames[section_id] = self._build_section(section_id)

        if self._current and self._current in self._frames:
            self._frames[self._current].pack_forget()
        self._frames[section_id].pack(fill="both", expand=True)
        self._current = section_id

        for sid, btn in self._buttons.items():
            btn.configure(
                bg=COLORS["active"] if sid == section_id else COLORS["secondary"]
            )
        label = next(lbl for sid, lbl, _ in self.SECTIONS if sid == section_id)
        self._status.set(f"Viewing: {label.strip()}")

    def _build_section(self, section_id: str) -> tk.Frame:
        frame = tk.Frame(self._content, bg=COLORS["light"])
        if section_id == "dashboard":
            self._build_dashboard(frame)
            return frame
        builder = self._builders.get(section_id)
        try:
            builder(frame)
        except Exception as exc:  # noqa: BLE001 — never let one module break the hub
            logger.exception("Finance hub: failed to build %s", section_id)
            tk.Label(
                frame,
                text=f"Could not load this section:\n{exc}",
                font=("Arial", 11), fg=COLORS["danger"], bg=COLORS["light"],
                justify="left",
            ).pack(expand=True, padx=20, pady=20)
        return frame

    # ── Dashboard ───────────────────────────────────────────────────

    def refresh_dashboard(self) -> None:
        """Rebuild the dashboard from fresh data and show it."""
        old = self._frames.pop("dashboard", None)
        if old is not None:
            old.destroy()
        if self._current == "dashboard":
            self._current = None
        self.show_section("dashboard")
        self._status.set("Dashboard refreshed")

    def _build_dashboard(self, frame: tk.Frame) -> None:
        tk.Label(
            frame, text="Finance Overview", font=("Arial", 16, "bold"),
            fg=COLORS["text"], bg=COLORS["light"], anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(
            frame, text="Headline figures across every finance area. "
            "Click a card to open that section.",
            font=("Arial", 10), fg=COLORS["muted"], bg=COLORS["light"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(2, 10))

        # Scrollable card area.
        canvas = tk.Canvas(frame, bg=COLORS["light"], highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        grid = tk.Frame(canvas, bg=COLORS["light"])
        grid.bind("<Configure>",
                  lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0))
        sb.pack(side="right", fill="y")

        cards = self._dashboard_cards()
        cols = 4
        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="cards")
        for idx, card in enumerate(cards):
            self._make_card(grid, idx // cols, idx % cols, **card)

    def _dashboard_cards(self) -> list[dict]:
        """Collect headline metrics; each module is isolated so one
        failure never blanks the whole dashboard."""
        cards: list[dict] = []

        def add(section, title, color, fn):
            try:
                value, subtitle = fn()
            except Exception:  # noqa: BLE001
                logger.exception("Finance hub: dashboard card %s failed", section)
                value, subtitle = "—", "unavailable"
            cards.append({"section": section, "title": title, "value": value,
                          "subtitle": subtitle, "color": color})

        def fees_card():
            s = fees_data.summary()
            return (_money(s.total_outstanding),
                    f"Outstanding  •  {s.overdue_count} overdue "
                    f"({_money(s.overdue_total)})")

        def bursaries_card():
            s = bursaries_data.summary()
            return (_money(s.total_remaining),
                    f"To disburse  •  {s.approved_active} active awards")

        def trips_card():
            s = trips_data.summary()
            return (_money(s.total_outstanding),
                    f"Outstanding  •  {s.upcoming_trips} upcoming, "
                    f"{s.active_bookings} bookings")

        def receipts_card():
            s = receipts_data.summary()
            return (_money(s.total_issued_amount),
                    f"Issued  •  {_money(s.daily_this_month)} this month")

        def expenses_card():
            s = expense_data.summary()
            open_n = s.submitted + s.under_review + s.approved
            return (_money(s.awaiting_payment_value),
                    f"Awaiting payment  •  {open_n} open claims")

        def funding_card():
            s = funding_data.summary()
            return (_money(s.total_remaining),
                    f"Remaining  •  {s.avg_utilisation_pct:.0f}% used, "
                    f"{s.overcommitted} over")

        def census_card():
            s = census_data.summary()
            return (str(s.open_windows),
                    f"Open windows  •  {s.overdue} overdue, "
                    f"{s.total_returns} returns")

        add("fees", "Fees & Payments", COLORS["danger"], fees_card)
        add("bursaries", "Bursaries", COLORS["success"], bursaries_card)
        add("trips", "Trips & Payments", COLORS["accent"], trips_card)
        add("receipts", "Receipts", COLORS["warning"], receipts_card)
        add("expenses", "Expense Claims", COLORS["accent"], expenses_card)
        add("funding", "Funding", COLORS["success"], funding_card)
        add("census", "Census / ILR", COLORS["warning"], census_card)
        return cards

    def _make_card(self, parent, row, col, *, section, title, value,
                   subtitle, color) -> None:
        card = tk.Frame(parent, bg=COLORS["card"], bd=0,
                        highlightthickness=1, highlightbackground="#d9dee1")
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        accent = tk.Frame(card, bg=color, height=4)
        accent.pack(fill="x")
        inner = tk.Frame(card, bg=COLORS["card"])
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        tk.Label(inner, text=title.upper(), font=("Arial", 9, "bold"),
                 fg=COLORS["muted"], bg=COLORS["card"], anchor="w",
                 ).pack(fill="x")
        tk.Label(inner, text=value, font=("Arial", 20, "bold"),
                 fg=color, bg=COLORS["card"], anchor="w",
                 ).pack(fill="x", pady=(4, 2))
        tk.Label(inner, text=subtitle, font=("Arial", 9),
                 fg=COLORS["text"], bg=COLORS["card"], anchor="w",
                 wraplength=240, justify="left").pack(fill="x")

        # Make the whole card a shortcut into its section.
        for w in (card, accent, inner, *inner.winfo_children()):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e, s=section: self.show_section(s))
