"""Integrity tab: declarations of interest.

* My declarations, with "Declare an interest" and "Declare no interests".
* To review – declarations by others that the signed-in person may review
  (the research office, or the declarer's head of department).
* Overdue – research staff with no declaration in the last year (office).

Data management plans are on each project (Projects tab).
"""

from __future__ import annotations

from tkinter import ttk

from education_system.systems.university.application.research import integrity as rules
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
)

_DECL_COLUMNS = [("declared", "Declared", 130), ("who", "Who", 130), ("kind", "Kind", 100),
                 ("counterpart", "With", 170), ("status", "Status", 90)]


def _values(row):
    return (row["declared_at"][:16], row["username"], common.nice(row["kind"]),
            row.get("counterpart"), common.nice(row["status"]))


class IntegrityTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        self._rows = {}
        top = ttk.Frame(self, padding=(6, 6, 6, 2))
        top.pack(side="top", fill="x")
        ttk.Button(top, text="Declare an interest", command=self.declare).pack(side="left",
                                                                               padx=3)
        ttk.Button(top, text="Declare no interests", command=self.declare_none).pack(
            side="left", padx=3)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=3)
        ttk.Label(top, text="Declare at least once a year, and whenever something changes.",
                  foreground="#555555").pack(side="left", padx=12)
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6, pady=4)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        self.book = ttk.Notebook(left)
        self.book.pack(fill="both", expand=True)
        self.mine = self._page("My declarations")
        self.review_bar = None
        self.to_review = self._page("To review", self._review_bar)
        self.overdue = None
        if self.who.is_office:
            page = ttk.Frame(self.book)
            self.book.add(page, text="  Overdue  ")
            self.overdue = common.make_tree(page, [("who", "Username", 130),
                                                   ("name", "Name", 200),
                                                   ("last", "Last declared", 160)])
        self.detail = common.Detail(right)
        self.detail.pack(fill="both", expand=True)
        self.detail.clear("Select a declaration.")

    def _page(self, title, bar=None):
        page = ttk.Frame(self.book)
        self.book.add(page, text=f"  {title}  ")
        if bar:
            bar(page)                                  # bottom bar packed first
        tree = common.make_tree(page, _DECL_COLUMNS)
        tree.bind("<<TreeviewSelect>>", lambda _e, t=tree: self._show(t))
        return tree

    def _review_bar(self, page):
        bar = ttk.Frame(page, padding=(0, 4))
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Review selected declaration", command=self.review).pack(
            side="left", padx=3)

    def refresh(self):
        mine = common.call(self, rules.declarations, self.who, mine=True) or []
        todo = common.call(self, rules.to_review, self.who) or []
        self._rows = {str(r["declaration_id"]): r for r in mine + todo}
        common.fill(self.mine, mine, lambda r: r["declaration_id"], _values)
        common.fill(self.to_review, todo, lambda r: r["declaration_id"], _values)
        self.book.tab(1, text=f"  To review ({len(todo)})  ")
        if self.overdue is not None:
            late = common.call(self, rules.overdue) or []
            common.fill(self.overdue, late, lambda r: r["username"],
                        lambda r: (r["username"], r["name"], r["last_declared"] or "never"))

    def open_record(self, declaration_id):
        self.refresh()
        key = str(declaration_id)
        for n, tree in enumerate((self.mine, self.to_review)):
            if tree.exists(key):
                self.book.select(n)
                tree.selection_set(key)
                tree.see(key)
                return

    def _show(self, tree):
        key = common.selected(tree)
        row = self._rows.get(key) if key else None
        if not row:
            return
        self.detail.show(f"Declaration {row['declaration_id']}", [
            ("", [("Who", row["username"]), ("Kind", common.nice(row["kind"])),
                  ("With", row.get("counterpart")), ("Value", common.money(row["value"])
                                                    if row.get("value") is not None else None),
                  ("Project", row.get("project_id")), ("Declared", row["declared_at"]),
                  ("Status", common.nice(row["status"])),
                  ("Reviewed by", row.get("reviewed_by")),
                  ("Reviewed", row.get("reviewed_at"))]),
            ("Description", row.get("description") or "—"),
            ("Management plan", row.get("management_plan") or "—"),
        ])

    def _project_choices(self):
        from education_system.systems.university.application.research import (
            projects as research_projects,
        )
        return [("", "(none)")] + (common.call(self, research_projects.choices, self.who,
                                               quiet=True) or [])

    def declare(self):
        data = common.ask(self, "Declare an interest", [
            Field("kind", "Kind", "combo", [k for k in rules.KINDS if k != "none"],
                  required=True),
            Field("counterpart", "Who it is with", required=True,
                  hint="company / organisation / person"),
            Field("description", "Description", "multiline", required=True),
            Field("value", "Value (£)", "number"),
            Field("project_id", "Related project", "combo", self._project_choices())])
        if data is None:
            return
        result = common.call(self, rules.declare, self.who, data["kind"],
                             counterpart=data["counterpart"], description=data["description"],
                             value=data["value"] if data["value"] != "" else None,
                             project_id=data["project_id"] or None, write=True)
        if result is not None:
            self.refresh()
            self.portal.changed()
            common.info(self, "Declared. It will be reviewed.")

    def declare_none(self):
        if not common.confirm(self, "Confirm you have no interests to declare?"):
            return
        if common.call(self, rules.declare, self.who, "none", write=True) is not None:
            self.refresh()
            self.portal.changed()

    def review(self):
        key = common.selected(self.to_review)
        if key is None:
            common.info(self, "Select a declaration to review.")
            return
        data = common.ask(self, "Review declaration", [
            Field("outcome", "Outcome", "combo", list(rules.REVIEW_OUTCOMES), required=True),
            Field("plan", "Management plan (needed when managed)", "multiline")])
        if data is None:
            return
        if common.call(self, rules.review, self.who, int(key), data["outcome"], data["plan"],
                       write=True) is not None:
            self.refresh()
            self.portal.changed()
