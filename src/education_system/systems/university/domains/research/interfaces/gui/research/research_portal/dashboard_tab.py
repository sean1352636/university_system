"""Dashboard: what needs doing, a few counts, and one search across areas."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.research import ethics
from education_system.systems.university.application.research import grants
from education_system.systems.university.application.research import ip
from education_system.systems.university.application.research import outputs
from education_system.systems.university.application.research import projects
from education_system.systems.university.application.research import reminders
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)


def _counts(conn, who) -> dict:
    out = {"Open ethics applications": sum(
        1 for r in ethics.listing(conn, who)
        if r["status"] in ethics.OPEN and who.me in (r.get("applicant_id"),
                                                     r.get("principal_investigator_id")))}
    if who.is_staff:
        mine = projects.listing(conn, who)
        if who.is_office:       # the office sees every project; count only its own
            mine = [p for p in mine if p.get("principal_investigator_id") == who.username]
        out["My projects"] = len(mine)
        out["My active grants"] = sum(1 for g in grants.listing(conn, who, "active")
                                      if g.get("principal_investigator_id") == who.username)
        out["My outputs with open-access problems"] = len(
            [o for o in outputs.listing(conn, who, mine=True)
             if o["oa_status"] not in ("compliant", "exception", "not in scope")])
    return out


def _search(conn, who, text) -> list[dict]:
    found = []
    for row in ethics.listing(conn, who, search=text):
        found.append({"area": "ethics", "id": row["review_id"],
                      "title": f"{row.get('reference') or ''} {row.get('title') or ''}",
                      "status": row["status"]})
    if not who.is_staff:
        return found
    for row in projects.listing(conn, who, search=text):
        found.append({"area": "project", "id": row["project_id"],
                      "title": f"{row.get('reference') or ''} {row['project_title']}",
                      "status": row.get("status")})
    for row in grants.listing(conn, who, search=text):
        found.append({"area": "grant", "id": row["application_id"], "title": row["grant_name"],
                      "status": row["status"]})
    for row in outputs.listing(conn, who, search=text):
        found.append({"area": "output", "id": row["publication_id"], "title": row["title"],
                      "status": row["oa_status"]})
    for row in ip.listing(conn, who, search=text):
        found.append({"area": "ip", "id": row["disclosure_id"],
                      "title": f"{row.get('reference') or ''} {row['title']}",
                      "status": row.get("status")})
    return found


class DashboardTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        self._todo_refs = {}
        self._hits = {}
        if self.who.is_office:
            bar = ttk.Frame(self, padding=(6, 4))
            bar.pack(side="bottom", fill="x")
            ttk.Button(bar, text="Send reminders now", command=self._reminders).pack(
                side="left", padx=3)
            ttk.Button(bar, text="Run PGR escalations", command=self._pgr).pack(
                side="left", padx=3)
        self.tiles = ttk.Frame(self, padding=(6, 6))
        self.tiles.pack(side="top", fill="x")
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=6, pady=4)
        left = ttk.LabelFrame(panes, text="Needs your attention", padding=4)
        right = ttk.LabelFrame(panes, text="Search everything", padding=4)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        self.todo = common.make_tree(left, [("area", "Area", 90), ("title", "What", 280),
                                            ("detail", "Detail", 260)])
        self.todo.bind("<Double-1>", lambda _e: self._open_todo())
        row = ttk.Frame(right)
        row.pack(side="top", fill="x")
        self.query = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.query, width=28)
        entry.pack(side="left", padx=(0, 4))
        entry.bind("<Return>", lambda _e: self._search())
        ttk.Button(row, text="Search", command=self._search).pack(side="left")
        self.hits = common.make_tree(right, [("area", "Area", 70), ("title", "Title", 260),
                                             ("status", "Status", 110)])
        self.hits.bind("<Double-1>", lambda _e: self._open_hit())

    def refresh(self):
        items = common.call(self, reminders.attention, self.who, quiet=True) or []
        self.todo.delete(*self.todo.get_children())
        self._todo_refs = {}
        for n, item in enumerate(items):
            self.todo.insert("", "end", iid=str(n), values=(item["area"], item["title"],
                                                            item["detail"] or ""))
            self._todo_refs[str(n)] = item.get("ref")
        if not items:
            self.todo.insert("", "end", iid="none", values=("", "Nothing needs you today", ""))
        for child in self.tiles.winfo_children():
            child.destroy()
        counts = common.call(self, _counts, self.who, quiet=True) or {}
        for label, value in counts.items():
            tile = ttk.LabelFrame(self.tiles, text=label, padding=(12, 4))
            tile.pack(side="left", padx=4)
            ttk.Label(tile, text=str(value), font=("Segoe UI", 16, "bold")).pack()

    def _open_todo(self):
        ref = self._todo_refs.get(common.selected(self.todo) or "")
        if ref:
            self.portal.show(ref[0], ref[1])

    def _search(self):
        text = self.query.get().strip()
        if not text:
            return
        rows = common.call(self, _search, self.who, text) or []
        self._hits = {}
        self.hits.delete(*self.hits.get_children())
        for n, row in enumerate(rows):
            self.hits.insert("", "end", iid=str(n), values=(
                row["area"], row["title"], common.nice(row["status"])))
            self._hits[str(n)] = (row["area"], row["id"])
        if not rows:
            self.hits.insert("", "end", iid="none", values=("", "No matches", ""))

    def _open_hit(self):
        ref = self._hits.get(common.selected(self.hits) or "")
        if ref:
            self.portal.show(*ref)

    def _reminders(self):
        result = common.call(self, reminders.run, write=True, force=True)
        if isinstance(result, dict):
            common.info(self, f"Reminders sent: {result['reminded']}\n"
                              f"Ethics approvals expired: {result['expired']}")
            self.refresh()

    def _pgr(self):
        result = common.call(self, lambda _conn: reminders.run_pgr_escalations())
        if result is not None:
            common.info(self, f"PGR escalations created: {0 if result is True else result}")
