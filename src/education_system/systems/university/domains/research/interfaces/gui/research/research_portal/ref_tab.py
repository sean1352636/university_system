"""REF preparation for one unit of assessment at a time: the summary and
its gaps, output review and selection, staff attribution, impact case
studies and environment statements. Rules: ``application/research/ref``."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.application.research import ref as rr
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
    nice,
)


class _Pane(ttk.Frame):
    """A list with its own action bar pinned to the bottom."""

    def __init__(self, parent, columns, buttons):
        super().__init__(parent)
        bar = ttk.Frame(self, padding=(0, 4))
        bar.pack(side="bottom", fill="x")
        for label, command in buttons:
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=3)
        self.tree = common.make_tree(self, columns, height=10)

    def chosen(self):
        return common.selected(self.tree)


class RefTab(ttk.Frame):
    def __init__(self, parent, portal):
        super().__init__(parent)
        self.portal = portal
        self.who = portal.who
        top = ttk.Frame(self, padding=(6, 6, 6, 2))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Unit of assessment").pack(side="left")
        self.uoa = tk.StringVar()
        box = ttk.Combobox(top, textvariable=self.uoa, values=rr.UOAS, width=10,
                           state="readonly")
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Export CSV", command=self.on_export).pack(side="left", padx=4)
        self.summary = tk.Text(self, height=4, wrap="word", relief="flat", padx=8,
                               font=("Segoe UI", 10), state="disabled")
        self.summary.tag_configure("bad", foreground="#b3261e")
        self.summary.pack(side="top", fill="x", padx=6)
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=6, pady=4)
        self.outputs = _Pane(book, [("title", "Output", 300), ("rating", "Agreed", 60),
                                    ("reviews", "Reviews", 120), ("selected", "Selected", 70),
                                    ("problems", "Why not selectable", 360)],
                             [("Add review", self.on_review), ("Set agreed rating", self.on_rate),
                              ("Select", lambda: self.on_select(True)),
                              ("Deselect", lambda: self.on_select(False))])
        self.staff = _Pane(book, [("name", "Name", 220), ("username", "Username", 120),
                                  ("fte", "FTE", 60)],
                           [("Attribute staff", self.on_attribute), ("Remove", self.on_unattribute)])
        self.cases = _Pane(book, [("title", "Impact case", 360), ("lead", "Lead", 140),
                                  ("status", "Status", 90), ("rating", "Rating", 60)],
                           [("New case", self.on_new_case), ("Edit case", self.on_edit_case)])
        self.env = _Pane(book, [("version", "Version", 70), ("by", "Drafted by", 140),
                                ("at", "Created", 140), ("text", "Statement", 520)],
                         [("Add new version", self.on_env)])
        for pane, label in zip(self._panes(), ("Outputs", "Staff", "Impact cases",
                                                "Environment")):
            book.add(pane, text=f"  {label}  ")
        self._outputs, self._cases = {}, {}

    # ── loading ──
    def refresh(self):
        if not self.uoa.get():
            active = common.call(self, rr.active_uoas, quiet=True) or []
            self.uoa.set(active[0] if active else rr.UOAS[0])
        uoa = self.uoa.get()
        data = common.call(self, _load, uoa)
        if data is None:
            return
        keep = {pane: pane.chosen() for pane in self._panes()}
        self._summary(data["summary"])
        self._outputs = {str(o["publication_id"]): o for o in data["outputs"]}
        common.fill(self.outputs.tree, data["outputs"], lambda o: o["publication_id"],
                    lambda o: (o["title"], o.get("quality_rating") or "",
                               _reviews(o["review"]), "yes" if o.get("ref_submitted") else "",
                               "; ".join(o["problems"]) or "ready"))
        common.fill(self.staff.tree, data["staff"], lambda s: s["username"],
                    lambda s: (s.get("name") or s["username"], s["username"], s["fte"]))
        self._cases = {str(c["id"]): c for c in data["cases"]}
        common.fill(self.cases.tree, data["cases"], lambda c: c["id"],
                    lambda c: (c["title"], c.get("lead_username") or "", nice(c["status"]),
                               c.get("quality_rating") or ""))
        common.fill(self.env.tree, data["env"], lambda e: e["id"],
                    lambda e: (e["version"], e.get("drafted_by_username") or "",
                               e["created_at"], " ".join(e["narrative_text"].split())[:200]))
        for pane, chosen in keep.items():
            if chosen is not None and pane.tree.exists(chosen):
                pane.tree.selection_set(chosen)
                pane.tree.see(chosen)

    def _panes(self):
        return (self.outputs, self.staff, self.cases, self.env)

    def _summary(self, s):
        text = (f"{s['uoa']}: {s['staff']} staff ({s['fte']} FTE) · outputs needed "
                f"{s['required_outputs']} · selected {s['selected']} of {s['outputs']} · "
                f"average rating {s['average_rating'] or '—'} (4*: {s['four_star']}, "
                f"3*: {s['three_star']}) · impact cases {s['impact_cases']} · environment "
                f"statement v{s['environment_version'] or '—'}\n")
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("end", text)
        if s["gaps"]:
            self.summary.insert("end", "Gaps: " + "; ".join(s["gaps"]), ("bad",))
        else:
            self.summary.insert("end", "No gaps.")
        self.summary.configure(state="disabled")

    def _done(self, result):
        if result is not None:
            self.refresh()
            self.portal.changed()

    # ── outputs ──
    def _output(self):
        oid = self.outputs.chosen()
        if oid is None:
            common.info(self, "Select an output first.")
        return oid

    def on_review(self):
        oid = self._output()
        if oid is None:
            return
        data = common.ask(self, "Internal review", [
            Field("score", "Score", "combo", [(n, f"{n}*") for n in range(4, -1, -1)],
                  required=True), Field("comment", "Comment", "multiline")])
        if data:
            self._done(common.call(self, rr.add_review, self.who, int(oid), int(data["score"]),
                                   data["comment"], write=True))

    def on_rate(self):
        oid = self._output()
        if oid is None:
            return
        rev = self._outputs[oid]["review"]
        data = common.ask(self, "Agreed rating", [
            Field("stars", f"Rating (reviews average {rev['mean'] or '—'})", "combo",
                  [(n, f"{n}*") for n in range(4, -1, -1)], required=True)])
        if data:
            self._done(common.call(self, rr.set_rating, self.who, int(oid), int(data["stars"]),
                                   write=True))

    def on_select(self, selected):
        oid = self._output()
        if oid is not None:
            self._done(common.call(self, rr.select, self.who, int(oid), selected, write=True))

    # ── staff ──
    def on_attribute(self):
        data = common.ask(self, f"Attribute staff to {self.uoa.get()}", [
            Field("username", "Member of staff", "staff", common.staff_choices(self),
                  required=True), Field("fte", "FTE", "number", required=True)], {"fte": 1})
        if data:
            self._done(common.call(self, rr.attribute, self.who, data["username"],
                                   self.uoa.get(), data["fte"], write=True))

    def on_unattribute(self):
        username = self.staff.chosen()
        if username is None:
            common.info(self, "Select a member of staff first.")
        elif common.confirm(self, f"Remove {username} from {self.uoa.get()}?"):
            self._done(common.call(self, rr.unattribute, self.who, username, write=True))

    # ── impact cases and environment ──
    def _case_fields(self):
        return [Field("title", "Title", required=True),
                Field("lead_username", "Lead", "staff", [("", "(none)"),
                                                         *common.staff_choices(self)]),
                Field("status", "Status", "combo", list(rr.CASE_STATUSES), required=True),
                Field("quality_rating", "Rating", "combo", ["", "4*", "3*", "2*", "1*", "0*"]),
                Field("summary", "Summary", "multiline"),
                Field("reach_significance", "Reach and significance", "multiline"),
                Field("beneficiaries", "Beneficiaries"),
                Field("evidence_links", "Evidence")]

    def on_new_case(self):
        data = common.ask(self, f"New impact case — {self.uoa.get()}", self._case_fields(),
                          {"status": "draft"})
        if data:
            self._done(common.call(self, rr.save_impact_case, self.who,
                                   {**data, "uoa": self.uoa.get()}, write=True))

    def on_edit_case(self):
        cid = self.cases.chosen()
        if cid is None:
            common.info(self, "Select an impact case first.")
            return
        data = common.ask(self, "Edit impact case", self._case_fields(), self._cases[cid])
        if data:
            self._done(common.call(self, rr.save_impact_case, self.who, data, int(cid),
                                   write=True))

    def on_env(self):
        latest = next(iter(common.call(self, rr.environment_statements, self.uoa.get(),
                                       quiet=True) or []), None)
        data = common.ask(self, f"Environment statement — {self.uoa.get()}", [
            Field("text", "Statement", "multiline", required=True)],
            {"text": latest["narrative_text"] if latest else ""})
        if data:
            self._done(common.call(self, rr.add_environment_statement, self.who,
                                   self.uoa.get(), data["text"], write=True))

    def on_export(self):
        uoa = self.uoa.get()
        path = filedialog.asksaveasfilename(
            parent=self, title="Export REF submission", defaultextension=".csv",
            initialfile=f"REF_{uoa.replace(' ', '')}.csv", filetypes=[("CSV", "*.csv")])
        if path:
            rows = common.call(self, rr.export, uoa, path)
            if rows is not None:
                common.info(self, f"Wrote {rows} row(s) to {path}")


def _load(conn, uoa):
    return {"summary": rr.uoa_summary(conn, uoa), "outputs": rr.candidates(conn, uoa),
            "staff": rr.staff(conn, uoa), "cases": rr.impact_cases(conn, uoa),
            "env": rr.environment_statements(conn, uoa)}


def _reviews(review):
    if not review["count"]:
        return "none"
    text = f"{review['count']} · mean {review['mean']}"
    return text + " · moderate" if review["needs_moderation"] else text
