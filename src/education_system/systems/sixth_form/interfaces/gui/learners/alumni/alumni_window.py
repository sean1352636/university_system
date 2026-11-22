"""Tkinter views for Sixth Form Alumni."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.interfaces.gui._ui import fit_when_shown
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import db as alumni_db

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

# Split into sibling modules (2026-10-22); every name is re-exported here
# so ``alumni_views.X`` keeps working for all importers.
from .views_records import (
    AlumniTab,
    SummaryTab,
)
from .views_programmes import (
    UnarchivedLeaversTab,
    EventsTab,
)
from .views_giving import (
    CampaignsTab,
    RecurringDonationsTab,
    DonorPipelineTab,
    FundsTab,
    BequestsTab,
    MatchedGivingTab,
)
from .views_reports import (
    ReportsTab,
    AdminTab,
)
from .views_engagement import (
    ChaptersTab,
    ReEngagementTab,
    MilestonesTab,
    LostContactTab,
    DirectoryTab,
)
from .views_careers import (
    EmployersTab,
    JobsBoardTab,
    InternshipsBoardTab,
    MentorMatchTab,
)
from .views_messaging import (
    TemplatesTab,
    DripTab,
    ABTestsTab,
    NewslettersTab,
    TrackingTab,
)
from .views_compliance import (
    SafeguardingAlertsTab,
    ReunionPlannerTab,
    NEETTab,
    DataQualityTab,
    DedupeBucketsTab,
    ErasureTab,
    WebhooksTab,
    CustomFieldsTab,
    HESATab,
)


class _SoloNotebook(ttk.Frame):
    """Frame that quacks like ``ttk.Notebook`` for existing tab
    classes. Each ``…Tab`` class does ``self.frame = ttk.Frame(nb);
    nb.add(self.frame, text=…)``; we accept ``add()`` and just pack
    the child, so the tab renders into a generic content pane with
    no tab-bar chrome."""

    def add(self, child: tk.Widget, text: str = "", **_: object) -> None:
        child.pack(fill="both", expand=True)


def _alumni_nav() -> list[tuple[str, list[tuple[str, type]]]]:
    """Top-level navigation, grouped by purpose. Built lazily so the
    Tab class names below resolve at call time, not import time."""
    return [
        ("Alumni records", [
            ("Alumni",             AlumniTab),
            ("Summary",            SummaryTab),
            ("Unarchived leavers", UnarchivedLeaversTab),
            ("Admin",              AdminTab),
        ]),
        ("Events", [
            ("Events",          EventsTab),
            ("Reunion planner", ReunionPlannerTab),
        ]),
        ("Fundraising", [
            ("Campaigns",      CampaignsTab),
            ("Recurring",      RecurringDonationsTab),
            ("Donor pipeline", DonorPipelineTab),
            ("Funds",          FundsTab),
            ("Bequests",       BequestsTab),
            ("Matched giving", MatchedGivingTab),
        ]),
        ("Career & network", [
            ("Chapters",            ChaptersTab),
            ("Employers",           EmployersTab),
            ("Jobs",                JobsBoardTab),
            ("Internships",         InternshipsBoardTab),
            ("Mentor match",        MentorMatchTab),
            ("Safeguarding alerts", SafeguardingAlertsTab),
        ]),
        ("Engagement & outreach", [
            ("Re-engagement",    ReEngagementTab),
            ("Milestones",       MilestonesTab),
            ("Lost contact",     LostContactTab),
            ("Public directory", DirectoryTab),
        ]),
        ("Communications", [
            ("Templates",   TemplatesTab),
            ("Drip",        DripTab),
            ("A/B tests",   ABTestsTab),
            ("Newsletters", NewslettersTab),
            ("Tracking",    TrackingTab),
        ]),
        ("Outcomes", [
            ("NEET",            NEETTab),
            ("HESA benchmarks", HESATab),
        ]),
        ("Reports & compliance", [
            ("Reports",        ReportsTab),
            ("Data quality",   DataQualityTab),
            ("Dedupe buckets", DedupeBucketsTab),
            ("Erasure",        ErasureTab),
            ("Webhooks",       WebhooksTab),
            ("Custom fields",  CustomFieldsTab),
        ]),
    ]


def open_alumni_window(parent=None) -> None:
    alumni_db.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Alumni — {branding.SYSTEM_NAME}")
    # Clamped to the screen: 1400x900 is bigger than a 1366x768 laptop,
    # which put the right-hand edge and the bottom of every page off it.
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)

    style = ttk.Style(win)
    # Reuse the main GUI's category-button look-and-feel if it has
    # been registered; otherwise create the style here so the alumni
    # window matches when launched stand-alone.
    try:
        style.configure("Category.TButton",
                          padding=8, font=("", 10, "bold"))
    except tk.TclError:
        pass

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=0)
    outer.columnconfigure(1, weight=1)
    outer.rowconfigure(0, weight=1)

    # ── Left-hand nav (collapsible categories) ──────────────────────
    nav = ttk.LabelFrame(outer, text="Navigation", padding=5)
    nav.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    nav.rowconfigure(0, weight=1)
    nav.columnconfigure(0, weight=1)

    nav_canvas = tk.Canvas(nav, highlightthickness=0, width=200)
    nav_canvas.grid(row=0, column=0, sticky="nsew")
    vs = ttk.Scrollbar(nav, orient="vertical",
                          command=nav_canvas.yview)
    vs.grid(row=0, column=1, sticky="ns")
    nav_canvas.configure(yscrollcommand=vs.set)

    inner = ttk.Frame(nav_canvas)
    nav_window = nav_canvas.create_window(
        (0, 0), window=inner, anchor="nw")
    inner.bind(
        "<Configure>",
        lambda _e: nav_canvas.configure(
            scrollregion=nav_canvas.bbox("all")))
    nav_canvas.bind(
        "<Configure>",
        lambda e: nav_canvas.itemconfigure(nav_window, width=e.width))

    # ── Right-hand content pane ─────────────────────────────────────
    content = ttk.Frame(outer, padding=5)
    content.grid(row=0, column=1, sticky="nsew")

    def _mount(tab_cls: type, label: str) -> None:
        """Clear the content pane and instantiate ``tab_cls`` into
        a fresh _SoloNotebook so the tab class's existing
        ``nb.add(...)`` call works unchanged."""
        for w in content.winfo_children():
            w.destroy()
        title = ttk.Label(content, text=label,
                            font=("", 12, "bold"))
        title.pack(anchor="w", pady=(0, 6))
        host = _SoloNotebook(content)
        host.pack(fill="both", expand=True)
        try:
            tab_cls(host)
        except Exception as exc:  # noqa: BLE001 - surface to user
            logger.exception("Failed to mount %s", tab_cls.__name__)
            messagebox.showerror("Open", str(exc))
            return
        # The pages were laid out for a wider window: wrap long button
        # rows, fit table columns and keep action bars on screen.
        fit_when_shown(host)

    def _make_category(label: str,
                          items: list[tuple[str, type]]) -> None:
        container = ttk.Frame(inner)
        container.pack(fill="x", pady=2, padx=5)
        state = {"expanded": False, "sub": None}
        btn = ttk.Button(container, text=f"{label}  ▶",
                            style="Category.TButton")
        btn.pack(fill="x")

        def toggle() -> None:
            if state["expanded"]:
                if state["sub"] is not None:
                    state["sub"].pack_forget()
                btn.configure(text=f"{label}  ▶")
                state["expanded"] = False
            else:
                if state["sub"] is None:
                    sub = ttk.Frame(container)
                    for item_label, tab_cls in items:
                        ttk.Button(
                            sub, text=item_label,
                            command=lambda c=tab_cls,
                                            lbl=item_label:
                                       _mount(c, lbl)
                            ).pack(fill="x", pady=1, padx=4)
                    state["sub"] = sub
                state["sub"].pack(fill="x", pady=(2, 4))
                btn.configure(text=f"{label}  ▼")
                state["expanded"] = True
            try:
                inner.update_idletasks()
                nav_canvas.configure(
                    scrollregion=nav_canvas.bbox("all"))
            except tk.TclError:
                pass

        btn.configure(command=toggle)

    for cat_label, cat_items in _alumni_nav():
        _make_category(cat_label, cat_items)

    # Open the Alumni list by default so the window isn't blank.
    _mount(AlumniTab, "Alumni")
