"""Reports: grants pipeline, ethics by status, open-access problems,
overdue declarations and (for the office) the research audit log."""

from __future__ import annotations

import csv
from tkinter import filedialog, ttk

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import ethics
from education_system.systems.university.application.research import grants
from education_system.systems.university.application.research import integrity
from education_system.systems.university.application.research import outputs
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)


def _summary(conn, who) -> dict:
    pipeline = grants.pipeline(conn, who)
    by_status: dict[str, int] = {}
    for row in ethics.listing(conn, who):
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    problems = outputs.oa_problems(conn, who)
    out = {"pipeline": pipeline, "ethics": by_status, "oa_problems": problems,
           "overdue": integrity.overdue(conn)}
    out["audit"] = ra.recent_audit(conn, 300) if who.is_office else []
    return out


class ReportsTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        self.data = None
        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=3)
        ttk.Button(bar, text="Export CSV", command=self._export).pack(side="left", padx=3)
        self.rate = ttk.Label(bar, text="")
        self.rate.pack(side="left", padx=12)
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=4, pady=4)
        self.status_tree = self._page(book, "Grants by status", [("status", "Status", 200),
                                                                 ("count", "Applications", 120)])
        self.dept_tree = self._page(book, "Grants by department", [
            ("department", "Department", 200), ("applications", "Applications", 110),
            ("requested", "Requested", 140), ("awarded", "Awarded", 140)])
        self.ethics_tree = self._page(book, "Ethics by status", [("status", "Status", 200),
                                                                 ("count", "Applications", 120)])
        self.oa_tree = self._page(book, "Open-access problems", [
            ("title", "Output", 320), ("type", "Type", 130), ("accepted", "Accepted", 100),
            ("oa", "Open-access status", 200)])
        self.overdue_tree = self._page(book, "Declarations overdue", [
            ("username", "Username", 140), ("name", "Name", 200), ("last", "Last declared", 160)])
        self.audit_tree = None
        if self.who.is_office:
            self.audit_tree = self._page(book, "Audit log", [
                ("at", "When", 140), ("actor", "Who", 110), ("entity", "Record", 120),
                ("action", "Action", 140), ("detail", "Detail", 360)])

    @staticmethod
    def _page(book, title, columns):
        frame = ttk.Frame(book, padding=4)
        book.add(frame, text=f"  {title}  ")
        return common.make_tree(frame, columns)

    def refresh(self):
        data = common.call(self, _summary, self.who, quiet=True)
        if data is None:
            return
        self.data = data
        pipe = data["pipeline"]
        common.fill(self.status_tree, [(s, n) for s, n in pipe["by_status"].items() if n],
                    lambda r: r[0], lambda r: (common.nice(r[0]), r[1]))
        common.fill(self.dept_tree, list(pipe["by_department"].items()), lambda r: r[0],
                    lambda r: (r[0], r[1]["applications"], common.money(r[1]["requested"]),
                               common.money(r[1]["awarded"])))
        rate = pipe["success_rate"]
        self.rate.configure(text="Grant success rate: " + ("—" if rate is None else f"{rate}%"))
        common.fill(self.ethics_tree, sorted(data["ethics"].items()), lambda r: r[0],
                    lambda r: (common.nice(r[0]), r[1]))
        common.fill(self.oa_tree, data["oa_problems"], lambda r: r["publication_id"],
                    lambda r: (r["title"], r["publication_type"], r.get("acceptance_date"),
                               r["oa_status"]))
        common.fill(self.overdue_tree, data["overdue"], lambda r: r["username"],
                    lambda r: (r["username"], r["name"], r.get("last_declared") or "never"))
        if self.audit_tree is not None:
            common.fill(self.audit_tree, data["audit"], lambda r: r["audit_id"], lambda r: (
                r["at"], r.get("actor"), f"{r['entity']} {r['entity_id']}",
                common.nice(r["action"]), r.get("detail") or ""))

    def _rows(self):
        data = self.data
        pipe = data["pipeline"]
        yield ["section", "item", "value", "extra", "extra"]
        for status, n in pipe["by_status"].items():
            yield ["grants by status", status, n, "", ""]
        for dept, d in pipe["by_department"].items():
            yield ["grants by department", dept, d["applications"], d["requested"], d["awarded"]]
        yield ["grants", "success rate %", pipe["success_rate"], "", ""]
        for status, n in sorted(data["ethics"].items()):
            yield ["ethics by status", status, n, "", ""]
        for o in data["oa_problems"]:
            yield ["open access", o["title"], o["oa_status"], o.get("acceptance_date"),
                   o.get("deposit_date")]
        for o in data["overdue"]:
            yield ["declaration overdue", o["username"], o["name"], o.get("last_declared"), ""]

    def _export(self):
        if self.data is None:
            self.refresh()
        if self.data is None:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export research summary",
                                            defaultextension=".csv",
                                            initialfile="research_summary.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(self._rows())
        except OSError as exc:
            common.info(self, f"Could not write the file: {exc}")
            return
        common.info(self, f"Saved {path}")
