"""Search tab — constructor, layout and running searches.

Moved verbatim from ``advanced_search_views``.
"""

from __future__ import annotations

import random
import re
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    engine as search_engine,
    history as search_history,
    insights as search_insights,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    QueryOptions,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)
from ._widgets import (
    _ROW_TAG_COLOURS,
    _load_ui_store,
    _save_ui_store,
    _nl_to_query,
    _lint_query,
    _choose_from,
)
from education_system.systems.sixth_form.interfaces.gui._sidebar import (
    SidebarBook,
    action_list,
    page_header,
)
from .search_actions import _ActionsMixin
from .search_results import _ResultsMixin


# ══ Search tab ═════════════════════════════════════════════════════

class SearchTab(_ResultsMixin, _ActionsMixin):
    """The Search page plus the pages that tune it.

    With a :class:`SidebarBook` the controls are spread over six sidebar
    pages (Search, Scopes & Filters, Query Tools, View & Layout,
    Shortlist & Recent, Bulk & Triage). ``self.frame`` is always the
    Search page, which keeps the query bar, results and preview.
    """

    def __init__(self, nb) -> None:
        self._nb = nb
        self.frame = ttk.Frame(nb)
        self._scope_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _add_page(self, frame: tk.Misc, text: str, group: str,
                  on_show=None) -> None:
        if isinstance(self._nb, SidebarBook):
            self._nb.add(frame, text=text, group=group, on_show=on_show)
        else:
            self._nb.add(frame, text=text)

    def _new_page(self, text: str, group: str, title: str, blurb: str,
                  on_show=None) -> ttk.Frame:
        page = ttk.Frame(self._nb)
        self._add_page(page, text, group, on_show)
        page_header(page, title, blurb)
        return page

    def _show_search(self) -> None:
        if hasattr(self._nb, "select"):
            self._nb.select(self.frame)

    def _then_search_page(self, command):
        """Run *command*, then show the Search page where its effect is."""
        def run() -> None:
            command()
            self._show_search()
        return run

    def _search_now(self) -> None:
        self._show_search()
        self.run()

    def _build(self) -> None:
        self._add_page(self.frame, "Search", "Search",
                       on_show=self._refresh_summary)
        self._build_search_page()
        self._build_filters_page()
        self._build_query_page()
        self._build_view_page()
        self._build_shortlist_page()
        self._build_bulk_page()
        self._bind_keys()
        self._refresh_summary()
        self._rebuild_qchips()               # restore pinned-query chips (23)

    # ── Search page ───────────────────────────────────────────────────

    def _build_search_page(self) -> None:
        page = self.frame
        # Query row
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Query:").pack(side="left")
        self.query_e = ttk.Entry(bar, width=44)
        self.query_e.pack(side="left", padx=(4, 8), fill="x", expand=True)
        self.query_e.bind("<Return>", lambda _e: self.run())
        self.query_e.bind("<KeyRelease>", self._on_query_key)
        ttk.Label(bar, text="Limit/scope:").pack(side="left")
        self.limit_e = ttk.Entry(bar, width=6)
        self.limit_e.insert(0, str(DEFAULT_LIMIT_PER_SCOPE))
        self.limit_e.pack(side="left", padx=(2, 8))
        # (4) Regex mode (also drives within-results + lint semantics)
        self.regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Regex", variable=self.regex_var,
                        command=self._update_lint).pack(side="left",
                                                        padx=(0, 8))
        ttk.Button(bar, text="Search",
                   command=self.run).pack(side="left")
        ttk.Button(bar, text="Clear",
                   command=self._clear).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Syntax…",
                   command=self._show_syntax).pack(side="left", padx=(4, 0))

        # What the next search covers, with a way to change it.
        summ = ttk.Frame(page)
        summ.pack(fill="x", pady=(0, 4))
        self.summary_var = tk.StringVar(value="")
        ttk.Label(summ, textvariable=self.summary_var,
                  foreground="#555").pack(side="left")
        ttk.Button(summ, text="Change scopes & filters…",
                   command=lambda: self._nb.select(self._filters_page)
                   ).pack(side="left", padx=(8, 0))
        # (6) Query lint indicator (updates as you type)
        self.lint_var = tk.StringVar(value="")
        ttk.Label(summ, textvariable=self.lint_var,
                  foreground="#b26a00", anchor="e").pack(side="right")

        # Pinned-query chips (feature 23)
        self.qchip_frame = ttk.Frame(page)
        self.qchip_frame.pack(fill="x")
        # Suggested-filter facet chips (item 47).
        self.facet_frame = ttk.Frame(page)
        self.facet_frame.pack(fill="x")
        # Did-you-mean row (item 20 of the previous batch).
        self.sugg_frame = ttk.Frame(page)
        self.sugg_frame.pack(fill="x")

        # Bulk-actions toolbar (item 20). Packed at the bottom *before*
        # the results split so the split cannot push it off-screen.
        actions = ttk.Frame(page)
        actions.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(actions, text="Open",
                   command=self._open_selected).pack(side="left")
        ttk.Button(actions, text="Copy IDs",
                   command=self._copy_ids).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Copy emails",
                   command=self._copy_emails).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Export…",
                   command=self._export_results_dialog).pack(
            side="left", padx=(4, 0))
        ttk.Button(actions, text="Message…",
                   command=self._mailmerge_dialog).pack(side="left",
                                                        padx=(4, 0))
        ttk.Button(actions, text="Contact sheet",
                   command=self._contact_sheet).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Pin",
                   command=self._pin_selected).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Shortlist +",
                   command=self._add_to_shortlist).pack(side="left",
                                                        padx=(4, 0))
        ttk.Button(actions, text="Save as cohort…",
                   command=self._save_cohort).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Bulk & triage…",
                   command=lambda: self._nb.select(self._bulk_page)
                   ).pack(side="right")

        # Results header: stats, expand/collapse and pagination (15, 16, 22)
        head = ttk.Frame(page)
        head.pack(fill="x", pady=(2, 2))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(head, textvariable=self.stats_var,
                  anchor="w").pack(side="left")
        ttk.Button(head, text="Next ▶", width=7,
                   command=self._next_page).pack(side="right")
        self.page_var = tk.StringVar(value="")
        ttk.Label(head, textvariable=self.page_var, width=14,
                  anchor="center").pack(side="right")
        ttk.Button(head, text="◀ Prev", width=7,
                   command=self._prev_page).pack(side="right")
        self.page_size_var = tk.StringVar(value="All")
        psz = ttk.Combobox(head, textvariable=self.page_size_var, width=6,
                           state="readonly",
                           values=["25", "50", "100", "250", "All"])
        psz.pack(side="right", padx=(0, 6))
        psz.bind("<<ComboboxSelected>>", lambda _e: self._on_page_size())
        ttk.Label(head, text="Page size:").pack(side="right", padx=(12, 2))
        ttk.Button(head, text="Collapse all", width=11,
                   command=self._collapse_all).pack(side="right", padx=(2, 0))
        ttk.Button(head, text="Expand all", width=10,
                   command=self._expand_all).pack(side="right")
        self._page = 0

        # Main split: results (left) + preview (right) (19)
        paned = ttk.Panedwindow(page, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=(0, 2))
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)
        self._cols = ("entity_id", "label", "sublabel", "match")
        self._col_titles = {"entity_id": "ID", "label": "Label",
                            "sublabel": "Details", "match": "Match"}
        # Column ordering (12) + pinned/frozen-to-front columns (17).
        self._col_order = list(self._cols)
        self._pinned_cols: set[str] = set()
        self._display_cols = list(self._cols)
        # Dedicated style so row-density (13) changes don't leak to other
        # treeviews in the app.
        self._tree_style = ttk.Style()
        self._tree_style.configure("AdvSearch.Treeview", rowheight=22)
        self.tree = ttk.Treeview(table_frame, columns=self._cols,
                                 show="tree headings",
                                 style="AdvSearch.Treeview")
        self.tree.heading("#0", text="Group")
        for c in self._cols:
            self.tree.heading(
                c, text=self._col_titles[c],
                command=lambda cc=c: self._sort_by(cc))
        self.tree.column("#0", width=150, anchor="w")
        self.tree.column("entity_id", width=80, anchor="w")
        self.tree.column("label", width=260, anchor="w")
        self.tree.column("sublabel", width=360, anchor="w")
        self.tree.column("match", width=150, anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("scope", background="#eef7ff",
                                font=("", 10, "bold"))
        # Conditional row-colour tags (feature 14).
        for _tag, _bg in _ROW_TAG_COLOURS.items():
            self.tree.tag_configure(_tag, background=_bg)
        # Heatmap buckets (feature 13) — cool→warm by score.
        for _i, _bg in enumerate(
                ("#e8f0ff", "#e6f7ec", "#fff7d6", "#ffe6cc", "#ffd6d6")):
            self.tree.tag_configure(f"heat{_i}", background=_bg)
        # Diff-since-last-run highlight (feature 4).
        self.tree.tag_configure("row-new", background="#d9f2ff",
                                font=("", 10, "bold"))

        # Preview pane (item 19)
        prev_frame = ttk.LabelFrame(paned, text="Preview", padding=4)
        paned.add(prev_frame, weight=1)
        self.preview = tk.Text(prev_frame, wrap="word", width=38, height=6,
                               font=("TkFixedFont", 9), state="disabled")
        self.preview.pack(fill="both", expand=True)

        # Status bar: under the whole window when there is a sidebar, so
        # messages from actions on the other pages are seen too.
        self.status_var = tk.StringVar(value="Ready.  (/ to focus, "
                                              "Enter to search, "
                                              "double-click to open, "
                                              "type to jump)")
        status_parent = self._nb.master if isinstance(
            self._nb, SidebarBook) else page
        status = ttk.Label(status_parent, textvariable=self.status_var,
                           anchor="w", relief="sunken", padding=(6, 2))
        if status_parent is page:
            status.pack(side="bottom", fill="x", before=actions)
        else:
            status.pack(side="bottom", fill="x", padx=10, pady=(0, 6),
                        before=self._nb)

    def _refresh_summary(self) -> None:
        """One line on the Search page saying what the next search covers."""
        if not hasattr(self, "summary_var"):
            return
        picked = self._selected_scopes()
        if len(picked) == len(self._scope_vars):
            parts = ["Searching all areas"]
        elif not picked:
            parts = ["No areas selected"]
        elif len(picked) <= 3:
            parts = ["Searching " + ", ".join(SCOPE_LABELS[k] for k in picked)]
        else:
            parts = [f"Searching {len(picked)} of {len(self._scope_vars)} areas"]
        for label, entry in (("Year", getattr(self, "year_e", None)),
                             ("Tutor group", getattr(self, "tg_e", None)),
                             ("Postcode", getattr(self, "pc_e", None)),
                             ("Staff", getattr(self, "owner_e", None))):
            value = entry.get().strip() if entry is not None else ""
            if value:
                parts.append(f"{label} {value}")
        for label, name in (("SEN only", "sen_var"),
                            ("including archived", "arch_var"),
                            ("redacted", "redact_var"),
                            ("live", "live_var")):
            var = getattr(self, name, None)
            if var is not None and var.get():
                parts.append(label)
        self.summary_var.set("  ·  ".join(parts))

    # ── Scopes & Filters page ─────────────────────────────────────────

    def _build_filters_page(self) -> None:
        page = self._filters_page = self._new_page(
            "Scopes & Filters", "Search", "Scopes & Filters",
            "Choose which areas are searched and narrow the results. "
            "These apply to the next search.")

        # Scopes (which areas are searched)
        scopes_frame = ttk.LabelFrame(page, text="Areas to search",
                                      padding=8)
        scopes_frame.pack(fill="x", pady=(0, 8))
        btns = ttk.Frame(scopes_frame)
        btns.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Button(btns, text="All",
                   command=self._select_all_scopes).pack(side="left")
        ttk.Button(btns, text="None",
                   command=self._select_no_scopes).pack(side="left",
                                                        padx=(4, 0))
        for i, key in enumerate(ALL_SCOPES):
            var = tk.BooleanVar(value=True)
            self._scope_vars[key] = var
            ttk.Checkbutton(scopes_frame, text=SCOPE_LABELS[key],
                            variable=var).grid(row=1 + i // 4, column=i % 4,
                                               sticky="w", padx=(0, 24),
                                               pady=1)

        # Filters (items 23–30)
        filt = ttk.LabelFrame(page, text="Narrow by", padding=8)
        filt.pack(fill="x", pady=(0, 8))
        self.year_e = ttk.Entry(filt, width=8)
        self.tg_e = ttk.Entry(filt, width=12)
        self.role_e = ttk.Entry(filt, width=12)
        self.owner_e = ttk.Entry(filt, width=12)
        self.actor_e = ttk.Entry(filt, width=12)
        self.pc_e = ttk.Entry(filt, width=8)
        for col, (label, entry) in enumerate((
                ("Year:", self.year_e), ("Tutor group:", self.tg_e),
                ("Role:", self.role_e), ("Staff:", self.owner_e),
                ("Actor:", self.actor_e), ("Postcode:", self.pc_e))):
            ttk.Label(filt, text=label).grid(row=col // 3, column=col % 3 * 2,
                                             sticky="e", pady=1)
            entry.grid(row=col // 3, column=col % 3 * 2 + 1, sticky="w",
                       padx=(2, 12), pady=1)
        # Role and actor are the signed-in account's: shown, not typed,
        # because they decide which gated areas are searched and whose
        # history and pins are used.
        self._show_identity()
        self.sen_var = tk.BooleanVar(value=False)
        self.arch_var = tk.BooleanVar(value=False)
        inc = ttk.Frame(filt)
        inc.grid(row=2, column=0, columnspan=10, sticky="w", pady=(8, 0))
        ttk.Checkbutton(inc, text="SEN only",
                        variable=self.sen_var).pack(side="left")
        ttk.Checkbutton(inc, text="Include archived records",
                        variable=self.arch_var).pack(side="left", padx=(16, 0))

        # Result ordering
        order = ttk.LabelFrame(page, text="Ordering & matching", padding=8)
        order.pack(fill="x", pady=(0, 8))
        self.interleave_var = tk.BooleanVar(value=False)
        self.cluster_var = tk.BooleanVar(value=False)
        self.fold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(order, text="Interleave by score",
                        variable=self.interleave_var).pack(side="left")
        ttk.Checkbutton(order, text="Cluster by student",
                        variable=self.cluster_var).pack(side="left",
                                                        padx=(16, 0))
        ttk.Checkbutton(order, text="Fold accents",
                        variable=self.fold_var).pack(side="left", padx=(16, 0))
        # Live search (item 42)
        self.live_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(order, text="Live (search as you type)",
                        variable=self.live_var).pack(side="left", padx=(16, 0))
        self._live_after = None

        # Security controls (items 31, 35)
        sec = ttk.LabelFrame(page, text="Privacy", padding=8)
        sec.pack(fill="x", pady=(0, 8))
        self.redact_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sec, text="Redact sensitive",
                        variable=self.redact_var).pack(side="left")
        ttk.Label(sec, text="Break-glass reason:").pack(side="left",
                                                        padx=(16, 2))
        self.bg_e = ttk.Entry(sec, width=40)
        self.bg_e.pack(side="left")

        foot = ttk.Frame(page)
        foot.pack(fill="x", pady=(4, 0))
        ttk.Button(foot, text="Search now",
                   command=self._search_now).pack(side="left")
        # (9) Filter presets — filter widgets only, named & reusable
        self._preset_mb = ttk.Menubutton(foot, text="Filter presets ▾")
        self._preset_menu = tk.Menu(self._preset_mb, tearoff=False,
                                    postcommand=self._rebuild_preset_menu)
        self._preset_mb.configure(menu=self._preset_menu)
        self._preset_mb.pack(side="left", padx=(8, 0))

    # ── Query Tools page ──────────────────────────────────────────────

    def _build_query_page(self) -> None:
        page = self._new_page(
            "Query Tools", "Search", "Query Tools",
            "Build, reuse and refine queries. Tools that change the query "
            "take you back to the Search page.")
        go = self._then_search_page
        # New-feature state (features 2, 4, 12, 13, 17, 21, 24)
        self.phonetic_var = tk.BooleanVar(value=False)   # feature 2
        self.diff_var = tk.BooleanVar(value=False)        # feature 4
        self.heatmap_var = tk.BooleanVar(value=False)     # feature 13
        self.safe_var = tk.BooleanVar(value=False)        # feature 24
        self.dark_var = tk.BooleanVar(value=False)        # feature 21
        self._cmp_slots: dict[str, dict] = {}             # feature 12
        self._ann_undo: list[tuple[str, str]] = []        # feature 17

        action_list(page, "Build a query", [
            ("Boolean builder…", "Combine terms with AND / OR / NOT.",
             go(self._boolean_builder)),
            ("Natural language…", "Type a question in plain English.",
             go(self._natural_language_query)),
            ("Regex tester…", "Try a regular expression before searching.",
             self._regex_tester),
            ("Negate last term", "Turn the last word into an exclusion.",
             go(self._negate_last_term)),
            ("Voice query 🎤", "Speak the query instead of typing it.",
             go(self._voice_query)),
        ])
        match = ttk.LabelFrame(page, text="Matching", padding=8)
        match.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(match, text="Phonetic / fuzzy match (sounds-like "
                                    "names)",
                        variable=self.phonetic_var,
                        command=self._toggle_phonetic).pack(anchor="w")

        reuse = ttk.LabelFrame(page, text="Reuse", padding=8)
        reuse.pack(fill="x", pady=(0, 8))
        # (1) Query templates — query + scopes + filters, named & reusable
        self._tpl_mb = ttk.Menubutton(reuse, text="Templates ▾", width=16)
        self._tpl_menu = tk.Menu(self._tpl_mb, tearoff=False,
                                 postcommand=self._rebuild_template_menu)
        self._tpl_mb.configure(menu=self._tpl_menu)
        self._tpl_mb.grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(reuse, text="Query, scopes and filters saved together.",
                  foreground="#7f8c8d").grid(row=0, column=1, sticky="w",
                                             padx=(10, 0))
        # (2) Recent raw queries
        self._hist_mb = ttk.Menubutton(reuse, text="Recent queries ▾",
                                       width=16)
        self._hist_menu = tk.Menu(self._hist_mb, tearoff=False,
                                  postcommand=self._rebuild_history_menu)
        self._hist_mb.configure(menu=self._hist_menu)
        self._hist_mb.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(reuse, text="Queries you ran recently.",
                  foreground="#7f8c8d").grid(row=1, column=1, sticky="w",
                                             padx=(10, 0))
        # Watchlists (feature 19)
        w_mb = ttk.Menubutton(reuse, text="Watchlists ▾", width=16)
        self._watch_menu = tk.Menu(w_mb, tearoff=False,
                                   postcommand=self._rebuild_watchlist_menu)
        w_mb.configure(menu=self._watch_menu)
        w_mb.grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(reuse, text="Queries you keep an eye on.",
                  foreground="#7f8c8d").grid(row=2, column=1, sticky="w",
                                             padx=(10, 0))
        ttk.Button(reuse, text="Pin query as chip", width=18,
                   command=go(self._pin_current_query)).grid(
            row=3, column=0, sticky="w", pady=2)
        ttk.Label(reuse, text="One-click chip above the results.",
                  foreground="#7f8c8d").grid(row=3, column=1, sticky="w",
                                             padx=(10, 0))

        refine = ttk.LabelFrame(page, text="Refine the current results",
                                padding=8)
        refine.pack(fill="x", pady=(0, 8))
        # (8) Search within current results
        ttk.Label(refine, text="Within:").pack(side="left")
        self.within_e = ttk.Entry(refine, width=24)
        self.within_e.pack(side="left", padx=(2, 4))
        self.within_e.bind("<Return>",
                           lambda _e: go(self._search_within_results)())
        ttk.Button(refine, text="Filter",
                   command=go(self._search_within_results)).pack(side="left")
        # (7) Random sample
        ttk.Button(refine, text="Random sample…",
                   command=go(self._random_sample)).pack(side="left",
                                                        padx=(16, 0))
        # (6) Estimate hit count
        ttk.Button(refine, text="Estimate hit count",
                   command=go(self._estimate_query)).pack(side="left",
                                                         padx=(4, 0))

    # ── View & Layout page ────────────────────────────────────────────

    def _build_view_page(self) -> None:
        page = self._new_page(
            "View & Layout", "Results", "View & Layout",
            "How the results table looks, plus pivots and comparisons.")

        lay = ttk.LabelFrame(page, text="Grouping & columns", padding=8)
        lay.pack(fill="x", pady=(0, 8))
        ttk.Label(lay, text="Group by:").pack(side="left")
        self.group_by = tk.StringVar(value="Scope")
        gb = ttk.Combobox(lay, textvariable=self.group_by, width=12,
                          state="readonly",
                          values=["Scope", "Year", "Tutor", "Risk",
                                  "Year+Risk", "Tutor+Risk", "Scope+Risk"])
        gb.pack(side="left", padx=(2, 12))
        gb.bind("<<ComboboxSelected>>", lambda _e: self._rerender())
        # (11) Flat vs grouped
        self.flat_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(lay, text="Flat list", variable=self.flat_var,
                        command=self._rerender).pack(side="left", padx=(0, 12))
        self._col_vars: dict[str, tk.BooleanVar] = {}
        colmb = ttk.Menubutton(lay, text="Columns ▾")
        colmenu = tk.Menu(colmb, tearoff=False)
        for key, lbl in (("entity_id", "ID"), ("label", "Label"),
                         ("sublabel", "Details"), ("match", "Match")):
            v = tk.BooleanVar(value=True)
            self._col_vars[key] = v
            colmenu.add_checkbutton(label=lbl, variable=v,
                                    command=self._apply_columns)
        colmb.configure(menu=colmenu)
        colmb.pack(side="left")
        # Column layouts (11)
        lay_mb = ttk.Menubutton(lay, text="Column layouts ▾")
        self._layout_menu = tk.Menu(lay_mb, tearoff=False,
                                    postcommand=self._rebuild_layout_menu)
        lay_mb.configure(menu=self._layout_menu)
        lay_mb.pack(side="left", padx=(4, 0))

        look = ttk.LabelFrame(page, text="Appearance", padding=8)
        look.pack(fill="x", pady=(0, 8))
        # (13) Row density
        ttk.Label(look, text="Density:").grid(row=0, column=0, sticky="w")
        self.density_var = tk.StringVar(value="Comfortable")
        dens = ttk.Combobox(look, textvariable=self.density_var, width=12,
                            state="readonly",
                            values=["Compact", "Comfortable", "Spacious"])
        dens.grid(row=0, column=1, sticky="w", padx=(2, 0))
        dens.bind("<<ComboboxSelected>>", lambda _e: self._apply_density())
        # (14) Conditional row colour
        self.colour_var = tk.BooleanVar(value=True)
        for row, (text, var, cmd) in enumerate((
                ("Colour by status/risk", self.colour_var, self._rerender),
                ("Heatmap by score", self.heatmap_var, self._toggle_heatmap),
                ("Highlight what is new since the last run", self.diff_var,
                 self._toggle_diff),
                ("Safe mode (mask sensitive)", self.safe_var,
                 self._toggle_safe),
                ("High-contrast dark theme", self.dark_var,
                 self._toggle_theme)), start=1):
            ttk.Checkbutton(look, text=text, variable=var,
                            command=cmd).grid(row=row, column=0,
                                              columnspan=2, sticky="w",
                                              pady=1)

        action_list(page, "Analyse", [
            ("Pivot — scope × status", "Counts of results by area and "
             "status.", self._pivot_view),
            ("Cross-scope overlap", "People who appear in more than one "
             "area.", self._cross_scope_overlap),
        ])
        # Compare (feature 12)
        action_list(page, "Compare two searches", [
            ("Capture as slot A", "Remember the current results.",
             lambda: self._snapshot_slot("A")),
            ("Capture as slot B", "Remember a second set of results.",
             lambda: self._snapshot_slot("B")),
            ("Show A vs B", "What was added and removed between them.",
             self._compare_slots),
        ])

    # ── Shortlist & Recent page ───────────────────────────────────────

    def _build_shortlist_page(self) -> None:
        page = self._new_page(
            "Shortlist & Recent", "Results", "Shortlist & Recent",
            "Records you set aside with Shortlist + on the Search page. "
            "The shortlist is kept across searches until you close the "
            "window.")
        # Shortlist tray (item 23)
        sl_frame = ttk.LabelFrame(page, text="Shortlist", padding=8)
        sl_frame.pack(fill="both", expand=True, pady=(0, 8))
        slb = ttk.Frame(sl_frame)
        slb.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(slb, text="Add selected results",
                   command=self._add_to_shortlist).pack(side="left")
        ttk.Button(slb, text="Open",
                   command=self._open_shortlisted).pack(side="left",
                                                        padx=(12, 0))
        ttk.Button(slb, text="Remove",
                   command=self._remove_shortlisted).pack(side="left",
                                                          padx=(4, 0))
        ttk.Button(slb, text="→Cohort",
                   command=self._shortlist_to_cohort).pack(side="left",
                                                           padx=(4, 0))
        ttk.Button(slb, text="Clear",
                   command=self._clear_shortlist).pack(side="left",
                                                       padx=(4, 0))
        sl_scroll = ttk.Scrollbar(sl_frame, orient="vertical")
        self.shortlist_box = tk.Listbox(sl_frame, height=10,
                                        selectmode="extended",
                                        yscrollcommand=sl_scroll.set)
        sl_scroll.configure(command=self.shortlist_box.yview)
        sl_scroll.pack(side="right", fill="y")
        self.shortlist_box.pack(side="left", fill="both", expand=True)
        self.shortlist_box.bind("<Double-1>",
                                lambda _e: self._open_shortlisted())
        self._shortlist: list[Hit] = []

        # Recent breadcrumb (item 25)
        rec = ttk.LabelFrame(page, text="Recently opened", padding=8)
        rec.pack(fill="x")
        self.recent_var = tk.StringVar()
        self.recent_combo = ttk.Combobox(
            rec, textvariable=self.recent_var, width=60, state="readonly")
        self.recent_combo.pack(side="left")
        self.recent_combo.bind("<<ComboboxSelected>>", self._reopen_recent)
        ttk.Label(rec, text="Pick one to open it again.",
                  foreground="#7f8c8d").pack(side="left", padx=(10, 0))
        self._recent: list[Hit] = []

    # ── Bulk & Triage page ────────────────────────────────────────────

    def _build_bulk_page(self) -> None:
        self._sel_var = tk.StringVar(value="")
        page = self._bulk_page = self._new_page(
            "Bulk & Triage", "Results", "Bulk & Triage",
            "These act on the rows selected in the results on the Search "
            "page.", on_show=self._refresh_selection_count)
        ttk.Label(page, textvariable=self._sel_var,
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w",
                                                           pady=(0, 8))
        # Bulk actions on the selection (features 21–25).
        action_list(page, "Change the selected records", [
            ("Tag selected…", "Add a tag to every selected row.",
             self._bulk_tag),
            ("Assign owner…", "Give the selected records a staff owner.",
             self._bulk_assign_staff),
            ("Set status…", "Students only.", self._bulk_status_change),
            ("Add note…", "Add the same note to each record.",
             self._bulk_add_note),
            ("Merge 2 duplicates…", "Students only: select exactly two.",
             self._merge_duplicates),
        ])
        action_list(page, "Triage", [
            ("Flag with reason…", "Flag the selection for follow-up.",
             self._bulk_flag),
            ("Assign to workflow…", "Send the selection to a workflow.",
             self._bulk_assign_workflow),
            ("PDF report for selection", "One report per selected record.",
             self._export_pdf_reports),
            ("Undo last bulk edit", "Reverse the most recent bulk change.",
             self._undo_bulk),
            ("Operator action log", "What has been done from this screen.",
             self._show_action_log),
        ])

    def _refresh_selection_count(self) -> None:
        n = len([i for i in self.tree.selection()
                 if "scope" not in self.tree.item(i, "tags")])
        self._sel_var.set(
            f"{n} row{'s' if n != 1 else ''} selected on the Search page."
            if n else "Nothing selected — select rows on the Search page "
                      "first.")

    # ── Keys ──────────────────────────────────────────────────────────

    def _bind_keys(self) -> None:
        if isinstance(self._nb, SidebarBook):
            self._nb.add_action("⌘ Command palette  (Ctrl+K)",
                                self._command_palette)
            self._nb.add_action("? Keyboard shortcuts  (F1)",
                                self._show_shortcuts)
        # Keyboard navigation + type-ahead jump (item 24)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<Return>", lambda _e: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Key>", self._type_ahead)
        # Column reorder/pin menu (12, 17), inline edit (18),
        # quick-look hover (19), jump-to-scope (20).
        self.tree.bind("<Button-3>", self._show_column_menu)
        self.tree.bind("<F2>", lambda _e: self._inline_edit())
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda _e: self._hide_quicklook())
        self.tree.bind("<Control-Right>", self._jump_next_scope)
        self.tree.bind("<Control-Left>", self._jump_prev_scope)
        self._ql_after = None
        self._ql_win: tk.Toplevel | None = None
        self._ql_row: str | None = None
        self.frame.bind_all("<slash>", self._focus_query)
        self.frame.bind_all("<Control-l>", self._focus_query)
        self.frame.bind_all("<Escape>", self._focus_query)
        self.query_e.bind("<Down>",
                          lambda _e: (self.tree.focus_set(),
                                      self._focus_first_hit()))
        self._typeahead_buf = ""
        self._sort_state: tuple[str, bool] | None = None
        self._last_results: SearchResults | None = None
        self._group_index: dict[str, tuple] = {}

        # Command palette (22) + shortcut cheatsheet (20) key bindings.
        self._build_command_registry()
        self.frame.bind_all("<Control-k>", self._command_palette)
        self.frame.bind_all("<F1>", self._show_shortcuts)
        # '?' opens the cheatsheet only from the results tree, so it never
        # interferes with typing '?' into the query box (regex quantifiers).
        self.tree.bind("<question>", self._show_shortcuts)

    def _selected_scopes(self) -> list[str]:
        return [k for k, v in self._scope_vars.items() if v.get()]

    def _select_all_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(True)

    def _select_no_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(False)

    def _clear(self) -> None:
        self.query_e.delete(0, "end")
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._show_suggestion("")
        for w in self.facet_frame.winfo_children():
            w.destroy()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self.stats_var.set("")
        self.status_var.set("Cleared.  (shortlist kept)")

    def _show_identity(self) -> None:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        p = access.current()
        for entry, value in ((self.role_e, p.job_role or p.role),
                             (self.actor_e, p.username)):
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, value or "(not signed in)")
            entry.configure(state="readonly")

    # Public API for other tabs to load a query into the search bar
    # and run it. *filters* is a saved search's filter dict.
    def load_query(self, query: str, scopes: list[str] | None,
                   filters: dict | None = None) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, query)
        if scopes is not None:
            for k, v in self._scope_vars.items():
                v.set(k in scopes)
        if filters is not None:
            self._apply_engine_filters(filters)
        self.run()

    def _apply_engine_filters(self, filters: dict) -> None:
        """Set the filter widgets from an engine filter dict (the form
        saved searches keep), clearing any filter it does not set."""
        for entry, key in ((self.year_e, "year_group"),
                           (self.tg_e, "tutor_group"),
                           (self.owner_e, "owned_by_staff"),
                           (self.pc_e, "postcode_prefix"),
                           (self.bg_e, "break_glass")):
            entry.delete(0, "end")
            entry.insert(0, str(filters.get(key) or ""))
        self.sen_var.set(bool(filters.get("sen_only")))
        self.arch_var.set(bool(filters.get("include_archived")))
        self.redact_var.set(bool(filters.get("redact")))
        self._refresh_summary()

    def current_filters(self) -> dict:
        """The engine filter dict the next search will use."""
        filters: dict[str, object] = {}
        for entry, key in ((self.year_e, "year_group"),
                           (self.tg_e, "tutor_group"),
                           (self.owner_e, "owned_by_staff"),
                           (self.pc_e, "postcode_prefix")):
            if entry.get().strip():
                filters[key] = entry.get().strip()
        if self.sen_var.get():
            filters["sen_only"] = True
        if self.arch_var.get():
            filters["include_archived"] = True
        if self.redact_var.get():
            filters["redact"] = True
        if self.bg_e.get().strip():
            filters["break_glass"] = self.bg_e.get().strip()
        return filters

    # ══ Query-tool features (1–10) ════════════════════════════════════

    # ── Shared filter-state helpers (used by templates + presets) ──────

    def _collect_filter_state(self) -> dict:
        return {
            "year": self.year_e.get(),
            "tutor_group": self.tg_e.get(),
            "owner": self.owner_e.get(),
            "postcode": self.pc_e.get(),
            "sen": self.sen_var.get(),
            "arch": self.arch_var.get(),
            "redact": self.redact_var.get(),
            "fold": self.fold_var.get(),
            "interleave": self.interleave_var.get(),
            "cluster": self.cluster_var.get(),
        }

    def _apply_filter_state(self, fs: dict) -> None:
        def _set(entry: ttk.Entry, val) -> None:
            entry.delete(0, "end")
            entry.insert(0, str(val or ""))
        _set(self.year_e, fs.get("year", ""))
        _set(self.tg_e, fs.get("tutor_group", ""))
        _set(self.owner_e, fs.get("owner", ""))
        _set(self.pc_e, fs.get("postcode", ""))
        self.sen_var.set(bool(fs.get("sen")))
        self.arch_var.set(bool(fs.get("arch")))
        self.redact_var.set(bool(fs.get("redact")))
        self.fold_var.set(bool(fs.get("fold", True)))
        self.interleave_var.set(bool(fs.get("interleave")))
        self.cluster_var.set(bool(fs.get("cluster")))

    def _results_from_hits(self, hits: list[Hit],
                           query: str) -> SearchResults:
        """Wrap a flat list of hits back into a SearchResults grouped by
        scope — used by regex/within/random which produce hit subsets."""
        by_scope: dict[str, list[Hit]] = {}
        for h in hits:
            by_scope.setdefault(h.scope, []).append(h)
        return SearchResults(
            query=query,
            scopes=list(by_scope.keys()) or self._selected_scopes(),
            hits_by_scope=by_scope, total=len(hits),
            ranked_hits=list(hits), suggestions=[])

    # ── (1) Query templates ────────────────────────────────────────────

    def _rebuild_template_menu(self) -> None:
        m = self._tpl_menu
        m.delete(0, "end")
        m.add_command(label="Save current as template…",
                      command=self._save_query_template)
        store = _load_ui_store()
        names = sorted(store["templates"])
        if names:
            m.add_command(label="Delete a template…",
                          command=self._delete_template)
            m.add_separator()
            for n in names:
                m.add_command(label=n,
                              command=lambda nn=n: self._apply_template(nn))
        else:
            m.add_separator()
            m.add_command(label="(no templates yet)", state="disabled")

    def _save_query_template(self) -> None:
        name = simpledialog.askstring("Save template", "Template name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        name = name.strip()
        store = _load_ui_store()
        store["templates"][name] = {
            "query": self.query_e.get().strip(),
            "scopes": self._selected_scopes(),
            "filters": self._collect_filter_state(),
        }
        _save_ui_store(store)
        self.status_var.set(f"Saved template {name!r}.")

    def _apply_template(self, name: str) -> None:
        tpl = _load_ui_store()["templates"].get(name)
        if not tpl:
            return
        self.query_e.delete(0, "end")
        self.query_e.insert(0, tpl.get("query", ""))
        scopes = tpl.get("scopes") or list(ALL_SCOPES)
        for k, v in self._scope_vars.items():
            v.set(k in scopes)
        self._apply_filter_state(tpl.get("filters", {}))
        self._update_lint()
        self.run()

    def _delete_template(self) -> None:
        store = _load_ui_store()
        name = _choose_from("Delete template", "Template to delete:",
                            sorted(store["templates"]), self.frame)
        if name and name in store["templates"]:
            del store["templates"][name]
            _save_ui_store(store)
            self.status_var.set(f"Deleted template {name!r}.")

    # ── (2) Recent query history ────────────────────────────────────────

    def _rebuild_history_menu(self) -> None:
        m = self._hist_menu
        m.delete(0, "end")
        try:
            entries = search_history.list_history(limit=40)
        except Exception:  # noqa: BLE001
            entries = []
        seen: set[str] = set()
        queries: list[str] = []
        for e in entries:
            qs = (e.query or "").strip()
            if qs and qs not in seen:
                seen.add(qs)
                queries.append(qs)
        if queries:
            for qs in queries[:20]:
                label = (qs[:60] + "…") if len(qs) > 60 else qs
                m.add_command(label=label,
                              command=lambda s=qs: self._use_history_query(s))
            m.add_separator()
            m.add_command(label="Clear history",
                          command=self._clear_history_confirm)
        else:
            m.add_command(label="(no history yet)", state="disabled")

    def _use_history_query(self, q: str) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, q)
        self._update_lint()
        self.run()

    def _clear_history_confirm(self) -> None:
        if messagebox.askyesno("Clear history",
                               "Delete your recorded search history?"):
            try:
                search_history.clear_history()
            except Exception:  # noqa: BLE001
                pass
            self.status_var.set("History cleared.")

    # ── (3) Natural-language query ──────────────────────────────────────

    def _natural_language_query(self) -> None:
        top = tk.Toplevel(self.frame.winfo_toplevel())
        top.title("Natural-language query")
        top.geometry("560x340")
        top.transient(self.frame.winfo_toplevel())
        ttk.Label(top, text="Describe what you're looking for:").pack(
            anchor="w", padx=10, pady=(10, 2))
        txt = tk.Text(top, height=4, wrap="word")
        txt.pack(fill="x", padx=10)
        txt.insert("1.0", "e.g. year 13 physics students with attendance "
                          "concerns")
        prev_var = tk.StringVar(value="")
        ttk.Label(top, text="Generated query:").pack(anchor="w", padx=10,
                                                     pady=(10, 2))
        ttk.Label(top, textvariable=prev_var, foreground="#0a5",
                  wraplength=520, justify="left").pack(anchor="w", padx=10)

        state: dict = {"q": "", "filters": {}}

        def _preview() -> None:
            q, filters = _nl_to_query(txt.get("1.0", "end"))
            state["q"], state["filters"] = q, filters
            bits = [f"query: {q!r}" if q else "query: (none)"]
            if filters:
                bits.append("filters: " + ", ".join(
                    f"{k}={v}" for k, v in filters.items()))
            prev_var.set("\n".join(bits))

        def _apply() -> None:
            _preview()
            q = state["q"]
            role = state["filters"].pop("role", None)
            if role:      # a staff job role is a query term, not an ACL role
                q = (q + " " + (f'role:"{role}"' if " " in role
                                else f"role:{role}")).strip()
            self.query_e.delete(0, "end")
            self.query_e.insert(0, q)
            self._apply_nl_filters(state["filters"])
            self._update_lint()
            top.destroy()
            self.run()

        btns = ttk.Frame(top)
        btns.pack(pady=12)
        ttk.Button(btns, text="Preview", command=_preview).pack(side="left",
                                                                padx=4)
        ttk.Button(btns, text="Apply & search", command=_apply).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=top.destroy).pack(side="left",
                                                                  padx=4)
        _preview()
        top.grab_set()

    def _apply_nl_filters(self, filters: dict) -> None:
        if "year_group" in filters:
            self.year_e.delete(0, "end")
            self.year_e.insert(0, str(filters["year_group"]))
        if "tutor_group" in filters:
            self.tg_e.delete(0, "end")
            self.tg_e.insert(0, str(filters["tutor_group"]))
        if filters.get("sen_only"):
            self.sen_var.set(True)

    # ── (4) Regex filtering ─────────────────────────────────────────────

    def _filter_results_regex(self, results: SearchResults,
                              pattern: str) -> SearchResults | None:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            messagebox.showerror("Invalid regex", str(exc))
            return None
        kept: list[Hit] = [
            h for h in results.all_hits()
            if rx.search(h.entity_id or "") or rx.search(h.label or "")
            or rx.search(h.sublabel or "")]
        return self._results_from_hits(kept, query=f"/{pattern}/")

    # ── (5) Negate last term ────────────────────────────────────────────

    def _negate_last_term(self) -> None:
        text = self.query_e.get()
        parts = text.split()
        if not parts:
            return
        last = parts[-1]
        parts[-1] = last[1:] if last.startswith("-") else "-" + last
        trailing = " " if text.endswith(" ") else ""
        self.query_e.delete(0, "end")
        self.query_e.insert(0, " ".join(parts) + trailing)
        self._update_lint()

    # ── (6) Query lint ──────────────────────────────────────────────────

    def _update_lint(self) -> None:
        if not hasattr(self, "lint_var"):
            return
        q = self.query_e.get().strip()
        if not q:
            self.lint_var.set("")
            return
        if getattr(self, "regex_var", None) and self.regex_var.get():
            try:
                re.compile(q)
                self.lint_var.set("regex ✓")
            except re.error as exc:
                self.lint_var.set(f"⚠ regex: {exc}")
            return
        warns = _lint_query(q)
        self.lint_var.set("⚠ " + "  ·  ".join(warns) if warns else "✓")

    # ── (7) Random sample ───────────────────────────────────────────────

    def _random_sample(self) -> None:
        n = simpledialog.askinteger(
            "Random sample", "How many records to sample?",
            initialvalue=10, minvalue=1, parent=self.frame)
        if not n:
            return
        if self._last_results is None:
            self.run()
        pool_res = self._last_results
        if pool_res is None:
            return
        pool = pool_res.all_hits()
        if not pool:
            self.status_var.set("No results to sample.")
            return
        sample = random.sample(pool, min(n, len(pool)))
        self._render(self._results_from_hits(
            sample, query=f"random {len(sample)} of {len(pool)}"))
        self.status_var.set(
            f"Showing a random {len(sample)} of {len(pool)} results.")

    # ── (8) Search within current results ───────────────────────────────

    def _search_within_results(self) -> None:
        term = self.within_e.get().strip()
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        if not term:
            self.status_var.set("Enter text to filter within results.")
            return
        if getattr(self, "regex_var", None) and self.regex_var.get():
            try:
                rx = re.compile(term, re.IGNORECASE)
            except re.error as exc:
                messagebox.showerror("Invalid regex", str(exc))
                return
            def match(s: str) -> bool:
                return bool(rx.search(s))
        else:
            needle = term.lower()
            def match(s: str) -> bool:
                return needle in s.lower()
        pool = self._last_results
        kept = [h for h in pool.all_hits()
                if match(h.entity_id or "") or match(h.label or "")
                or match(h.sublabel or "")]
        self._render(self._results_from_hits(
            kept, query=f"{pool.query}  (within: {term})"))
        self.status_var.set(
            f"{len(kept)} of {pool.total} matched {term!r} within results.")

    # ── (9) Filter presets ──────────────────────────────────────────────

    def _rebuild_preset_menu(self) -> None:
        m = self._preset_menu
        m.delete(0, "end")
        m.add_command(label="Save current filters…",
                      command=self._save_filter_preset)
        store = _load_ui_store()
        names = sorted(store["presets"])
        if names:
            m.add_command(label="Delete a preset…",
                          command=self._delete_preset)
            m.add_separator()
            for n in names:
                m.add_command(label=n,
                              command=lambda nn=n: self._apply_filter_preset(nn))
        else:
            m.add_separator()
            m.add_command(label="(no presets yet)", state="disabled")

    def _save_filter_preset(self) -> None:
        name = simpledialog.askstring("Save preset", "Preset name:",
                                      parent=self.frame)
        if not name or not name.strip():
            return
        name = name.strip()
        store = _load_ui_store()
        store["presets"][name] = self._collect_filter_state()
        _save_ui_store(store)
        self.status_var.set(f"Saved filter preset {name!r}.")

    def _apply_filter_preset(self, name: str) -> None:
        fs = _load_ui_store()["presets"].get(name)
        if fs is None:
            return
        self._apply_filter_state(fs)
        self.status_var.set(f"Applied filter preset {name!r}.")

    def _delete_preset(self) -> None:
        store = _load_ui_store()
        name = _choose_from("Delete preset", "Preset to delete:",
                            sorted(store["presets"]), self.frame)
        if name and name in store["presets"]:
            del store["presets"][name]
            _save_ui_store(store)
            self.status_var.set(f"Deleted preset {name!r}.")

    # ── (10) Voice query ────────────────────────────────────────────────

    def _voice_query(self) -> None:
        try:
            import speech_recognition as sr  # optional dependency
        except Exception:  # noqa: BLE001
            messagebox.showinfo(
                "Voice query",
                "Voice input needs the optional 'SpeechRecognition' package "
                "and a working microphone.\n\n"
                "Install with:\n    pip install SpeechRecognition pyaudio\n\n"
                "Then click 🎤 again to dictate your query.")
            return
        recogniser = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.status_var.set("Listening… speak your query.")
                self.frame.update()
                audio = recogniser.listen(source, timeout=5,
                                          phrase_time_limit=8)
            heard = recogniser.recognize_google(audio)
        except Exception as exc:  # noqa: BLE001
            messagebox.showwarning("Voice query",
                                   f"Could not capture audio: {exc}")
            self.status_var.set("Voice capture cancelled.")
            return
        self.query_e.delete(0, "end")
        self.query_e.insert(0, heard)
        self._update_lint()
        self.status_var.set(f"Heard: {heard!r} — press Enter to search.")

    def run(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.query_e.get().strip()
        scopes = self._selected_scopes()
        if not scopes:
            self.status_var.set("No scopes selected — pick at least one.")
            return
        try:
            limit = int(self.limit_e.get().strip()
                         or str(DEFAULT_LIMIT_PER_SCOPE))
        except ValueError:
            messagebox.showerror("Limit",
                                    "Limit must be a positive integer.")
            return
        filters = self.current_filters()
        self._show_identity()
        options = QueryOptions(fold_diacritics=self.fold_var.get())
        # Regex mode (feature 4): the query box holds a regex, not DSL.
        # Gather candidates with an empty DSL query over the same scopes
        # + filters, then post-filter by the pattern.
        regex_on = bool(getattr(self, "regex_var", None)
                        and self.regex_var.get())
        if regex_on and not q:
            self.status_var.set("Enter a regex pattern (Regex mode is on).")
            return
        try:
            results = search_engine.run_search(
                "" if regex_on else q, scopes=scopes, limit_per_scope=limit,
                filters=filters, options=options,
                interleave=self.interleave_var.get(),
                cluster_by_student=self.cluster_var.get())
        except ValidationError as e:
            messagebox.showerror("Search error", str(e))
            return
        if regex_on:
            filtered = self._filter_results_regex(results, q)
            if filtered is None:
                return
            results = filtered
        # Phonetic / fuzzy post-filter (feature 2).
        if (getattr(self, "phonetic_var", None) and self.phonetic_var.get()
                and q and not regex_on):
            results = self._filter_results_phonetic(results, q)
        # Diff-since-last-run bookkeeping (feature 4): which keys are new
        # versus the previous run of this same query string.
        cur_keys = {f"{h.scope}#{h.entity_id}" for h in results.all_hits()}
        prev = getattr(self, "_prev_keys_by_query", {}).get(results.query,
                                                            set())
        self._new_keys = cur_keys - prev if prev else set()
        if not hasattr(self, "_prev_keys_by_query"):
            self._prev_keys_by_query = {}
        self._prev_keys_by_query[results.query] = cur_keys
        self._render(results)

    def _render(self, results: SearchResults) -> None:
        self._last_results = results
        self._page = 0                       # new result set → first page
        self._rerender()
        self._render_facets(results)
        self._show_suggestion(
            results.suggestions[0]
            if results.total == 0 and results.suggestions else "")

    # ── Live search (item 42) ─────────────────────────────────────

    def _on_query_key(self, event) -> None:
        self._update_lint()
        if not getattr(self, "live_var", None) or not self.live_var.get():
            return
        if event.keysym in ("Return", "Up", "Down", "Left", "Right",
                            "Tab", "Escape"):
            return
        if self._live_after is not None:
            try:
                self.frame.after_cancel(self._live_after)
            except Exception:
                pass
        self._live_after = self.frame.after(400, self.run)

    # ── Suggested-filter facet chips (item 47) ────────────────────

    def _render_facets(self, results: SearchResults) -> None:
        for w in self.facet_frame.winfo_children():
            w.destroy()
        try:
            fcs = search_insights.facets(results, top=4)
        except Exception:
            fcs = []
        if not fcs:
            return
        ttk.Label(self.facet_frame, text="Narrow:").pack(side="left")
        shown = 0
        for f in fcs:
            for val, cnt in f.values:
                if shown >= 12:
                    return
                ttk.Button(
                    self.facet_frame, text=f"{f.field}:{val} ({cnt})",
                    command=lambda fl=f.field, v=val: self._apply_facet(fl, v)
                ).pack(side="left", padx=2)
                shown += 1

    def _apply_facet(self, field: str, value: str) -> None:
        add = f'{field}:"{value}"' if " " in value else f"{field}:{value}"
        cur = self.query_e.get().strip()
        self.query_e.delete(0, "end")
        self.query_e.insert(0, (cur + " " + add).strip())
        self.run()
