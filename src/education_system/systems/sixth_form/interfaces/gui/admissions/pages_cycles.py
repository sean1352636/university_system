"""Admissions window page: recruitment cycles.

One cycle per September intake (``2027/28``): its dates, how long
applicants have to answer an offer, results day and enrolment start,
and its status Planned → Open → Closed → Archived. Also the rollover
report, double applications within a cycle and re-applying a closed
application into a later cycle.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    cycles,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

TITLE = "Cycles"

_FIELDS: list[pc.Field] = [
    ("opens_on", "Applications open (YYYY-MM-DD)", "entry", None),
    ("closes_on", "Applications close (YYYY-MM-DD)", "entry", None),
    ("interview_from", "Interviews from", "entry", None),
    ("interview_to", "Interviews to", "entry", None),
    ("offer_response_days", "Days to answer an offer", "entry", None),
    ("results_day", "GCSE results day", "entry", None),
    ("enrolment_start", "Enrolment starts", "entry", None),
    ("notes", "Notes", "text", None),
]


class CyclesPage:
    COLS = [("cycle", "Cycle", 80), ("status", "Status", 80),
            ("opens", "Opens", 90), ("closes", "Closes", 90),
            ("interviews", "Interviews", 170), ("days", "Offer days", 75),
            ("results", "Results day", 90), ("enrol", "Enrolment", 90),
            ("apps", "Applications", 85), ("notes", "Notes", 240)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, TITLE, "Admissions cycles",
            "One cycle per September intake. Only an Open cycle takes new "
            "applications; two Open cycles cannot take applications on the "
            "same day. A Closed cycle can be reopened; nothing goes back to "
            "Planned.")
        self.editable = pc.can(access.ADMISSIONS)
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 2))
        st = "normal" if self.editable else "disabled"
        for text, cmd in (("New cycle…", self._new), ("Edit…", self._edit),
                          ("Open", lambda: self._status("Open")),
                          ("Close", lambda: self._status("Closed")),
                          ("Archive", lambda: self._status("Archived")),
                          ("Delete", self._delete)):
            ttk.Button(bar, text=text, command=cmd, state=st).pack(
                side="left", padx=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        bar2 = ttk.Frame(self.frame)
        bar2.pack(side="top", fill="x", pady=(0, 4))
        ttk.Button(bar2, text="Rollover report…",
                   command=self._rollover).pack(side="left", padx=(0, 4))
        ttk.Button(bar2, text="Double applications…",
                   command=self._duplicates).pack(side="left", padx=(0, 4))
        ttk.Button(bar2, text="Re-apply an applicant…", command=self._reapply,
                   state=st).pack(side="left", padx=(0, 4))
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=16)
        self.tree.tag_configure("Open", background="#d8f4d8")
        self.tree.tag_configure("Archived", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        self.refresh()

    # ── Loading ───────────────────────────────────────────────────

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, TITLE, cycles.list_cycles)
        if not ok:
            return
        counts: dict[str, int] = {}
        ok2, apps = pc.load(self.status, TITLE, adm.list_applicants)
        for a in apps or []:
            if a.intake_year:
                counts[a.intake_year] = counts.get(a.intake_year, 0) + 1
        for c in rows:
            window = ""
            if c.interview_from or c.interview_to:
                window = f"{c.interview_from or '?'} – {c.interview_to or '?'}"
            self.tree.insert("", "end", iid=c.cycle, tags=(c.status,), values=(
                c.cycle, c.status, c.opens_on, c.closes_on, window,
                c.offer_response_days, pc.fmt(c.results_day),
                pc.fmt(c.enrolment_start), counts.get(c.cycle, 0),
                (c.notes or "").replace("\n", " ")))
        if not ok2:
            return
        current = cycles.current_cycle()
        open_now = cycles.open_cycle_for()
        bits = [f"{len(rows)} cycle(s)"]
        bits.append(f"taking applications today: {open_now}" if open_now
                    else "no cycle is taking applications today")
        if current and current != open_now:
            bits.append(f"current cycle: {current}")
        unset = sorted(y for y in counts if y not in {c.cycle for c in rows})
        if unset:
            bits.append("applications for intakes with no cycle set up: "
                        + ", ".join(unset))
        self.status.set(" · ".join(bits))

    def _cycle(self) -> str | None:
        return pc.selected(self.tree, TITLE)

    # ── Actions ───────────────────────────────────────────────────

    def _new(self) -> None:
        latest = next(iter(pc.cycle_names()), None)
        name = (cycles.next_cycle_name(latest) if latest
                else adm.default_intake_year())
        fields: list[pc.Field] = [("cycle", "Cycle (e.g. 2027/28)", "entry",
                                   None)] + _FIELDS
        initial = {"cycle": name,
                   "offer_response_days": cycles.DEFAULT_OFFER_RESPONSE_DAYS}

        def submit(v: dict[str, Any]) -> None:
            cyc = v.pop("cycle")
            cycles.create_cycle(cyc, **v)

        if pc.ask_form(self.frame, "New admissions cycle", fields, initial,
                       on_submit=submit):
            self.refresh()

    def _edit(self) -> None:
        name = self._cycle()
        if not name:
            return
        c = cycles.get_cycle(name)
        if c is None:
            return
        if not self.editable:
            pc.show_text(self.frame, f"Cycle {name}", "\n".join(
                f"{label}: {pc.fmt(getattr(c, key))}"
                for key, label, _k, _o in _FIELDS))
            return
        initial = {k: getattr(c, k) for k, *_ in _FIELDS}
        if pc.ask_form(self.frame, f"Edit cycle {name} ({c.status})", _FIELDS,
                       initial, on_submit=lambda v: cycles.update_cycle(
                           name, **v)):
            self.refresh()

    def _status(self, status: str) -> None:
        name = self._cycle()
        if not name:
            return
        c = cycles.get_cycle(name)
        if c is None or c.status == status:
            return
        if status == "Open" and c.status == "Closed":
            verb = "Reopen"
        else:
            verb = {"Open": "Open", "Closed": "Close",
                    "Archived": "Archive"}[status]
        extra = ""
        if status == "Closed":
            extra = ("\n\nNew applications will no longer default to this "
                     "intake. Check the rollover report for applications "
                     "still open.")
        elif status == "Archived":
            extra = "\n\nAn archived cycle can no longer be changed."
        if not messagebox.askyesno(TITLE, f"{verb} cycle {name}?{extra}",
                                   parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, TITLE, cycles.set_cycle_status, name,
                       status)
        if ok:
            self.refresh()

    def _delete(self) -> None:
        name = self._cycle()
        if not name:
            return
        if not messagebox.askyesno(
                TITLE, f"Delete cycle {name}?\n\nOnly a Planned cycle with no "
                "applications can be deleted.",
                parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, TITLE, cycles.delete_cycle, name)
        if ok:
            self.refresh()

    def _rollover(self) -> None:
        sel = pc.selected(self.tree, TITLE, quiet=True)
        start = sel or pc.default_cycle()
        try:
            nxt = cycles.next_cycle_name(start)
        except ValueError:
            nxt = ""
        v = pc.ask_form(self.frame, "Rollover report", [
            ("from_cycle", "From cycle", "combo", pc.cycle_names()),
            ("to_cycle", "To cycle", "combo", pc.cycle_names()),
        ], {"from_cycle": start, "to_cycle": nxt})
        if not v:
            return
        ok, rep = pc.run(self.frame, "Rollover report", cycles.rollover_report,
                         v["from_cycle"], v["to_cycle"] or None)
        if not ok:
            return
        lines = list(rep.lines())

        def people(head: str, apps: list[adm.Applicant]) -> None:
            if apps:
                lines.extend(["", f"{head}:"])
                lines.extend(f"  {a.applicant_id}  {a.full_name}  ({a.status})"
                             for a in apps)

        people(f"Still open in {rep.from_cycle} (withdraw, defer or re-apply)",
               rep.still_open)
        people("Accepted, not yet enrolled", rep.accepted_not_enrolled)
        people(f"Deferred into {rep.to_cycle}", rep.deferred_in)
        if rep.reapplied:
            lines.extend(["", f"Re-applied for {rep.to_cycle}:"])
            lines.extend(f"  {old} → {new}" for old, new in rep.reapplied)
        if rep.duplicates_in_new:
            lines.extend(["", f"Possible double applications in "
                          f"{rep.to_cycle}:"])
            for i, g in enumerate(rep.duplicates_in_new, 1):
                lines.append(f"  {i}. " + "; ".join(
                    f"{a.applicant_id} {a.full_name}" for a in g))
        pc.show_text(self.frame, f"Rollover {rep.from_cycle} → {rep.to_cycle}",
                     "\n".join(lines), save_name="rollover_report.txt")

    def _duplicates(self) -> None:
        name = pc.selected(self.tree, TITLE, quiet=True) or pc.default_cycle()
        ok, groups = pc.run(self.frame, "Double applications",
                            cycles.duplicate_applications, name)
        if not ok:
            return
        if not groups:
            messagebox.showinfo(
                "Double applications",
                f"No double applications in {name}: each person has one "
                "application.", parent=self.frame.winfo_toplevel())
            return
        lines = [f"Double applications in {name} — one application per "
                 "person per cycle. Merge or withdraw the extra ones from "
                 "All Applicants.", ""]
        for i, g in enumerate(groups, 1):
            lines.append(f"Group {i}:")
            for a in g:
                lines.append(f"  {a.applicant_id}  {a.full_name}  "
                             f"{a.dob or ''}  {a.email or ''}  ({a.status}, "
                             f"submitted {a.submitted_at or '?'})")
            lines.append("")
        pc.show_text(self.frame, f"Double applications — {name}",
                     "\n".join(lines), save_name="double_applications.txt")

    def _reapply(self) -> None:
        ok, apps = pc.run(self.frame, "Re-apply", adm.list_applicants)
        if not ok:
            return
        eligible = [a for a in apps if a.status in cycles.REAPPLY_FROM
                    and not a.converted_student_id and not a.merged_into]
        if not eligible:
            messagebox.showinfo(
                "Re-apply", "No closed or waitlisted applications to re-apply "
                "from.", parent=self.frame.winfo_toplevel())
            return
        aid = pc.pick_row(
            self.frame, "Re-apply — choose the earlier application",
            [("id", "ID", 90), ("name", "Name", 200), ("status", "Status", 120),
             ("intake", "Intake", 80), ("school", "Previous school", 200)],
            [(a.applicant_id, (a.applicant_id, a.full_name, a.status,
                               a.intake_year or "", a.previous_school or ""))
             for a in eligible],
            prompt="Closed (rejected, withdrawn, declined) or waitlisted "
                   "applications. A waitlisted one is withdrawn first.")
        if not aid:
            return
        src = next(a for a in eligible if a.applicant_id == aid)
        later = [c for c in pc.cycle_names()
                 if not src.intake_year or c > src.intake_year]
        default = (cycles.next_cycle_name(src.intake_year)
                   if src.intake_year else pc.default_cycle())
        out: dict[str, Any] = {}

        def submit(v: dict[str, Any]) -> None:
            out["new"] = cycles.reapply(aid, v["to_cycle"],
                                        note=v["note"] or None)

        if pc.ask_form(
                self.frame, f"Re-apply {aid} {src.full_name}", [
                    ("to_cycle", "For cycle", "combo", later),
                    ("note", "Note", "text", None)],
                {"to_cycle": default}, on_submit=submit,
                intro="Copies details, profile, contacts, programme choices "
                      "and GCSEs. References, sensitive information and the "
                      "identity check must be gathered again."):
            new = out["new"]
            messagebox.showinfo(
                "Re-apply", f"New application {new.applicant_id} for "
                f"{new.intake_year} ({new.status}).",
                parent=self.frame.winfo_toplevel())
            self.refresh()


def build(nb: Any) -> CyclesPage:
    return CyclesPage(nb)

