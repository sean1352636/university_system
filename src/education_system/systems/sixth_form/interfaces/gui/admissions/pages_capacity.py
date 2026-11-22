"""Admissions window pages: places, oversubscription criteria, feeder schools.

* **Places & Capacity** — places per programme for a cycle (set or
  clear the limit), places held / left, offers against capacity, the
  oversubscription ranking for one programme and a CSV export.
* **Oversubscription** — the order the criteria are applied in and which
  are switched on (home-to-college distance is listed but cannot be used).
* **Feeder Schools** — partner schools and the guaranteed-place scheme,
  and applying the scheme to a cycle's open applications.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions_insights as insights,
    capacity,
    programme_choices,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    pages_common as pc,
)

PLACES = "Places & Capacity"
CRITERIA = "Oversubscription"
FEEDERS = "Feeder Schools"


def _subjects() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects_mod,
        )
        return sorted({s.name for s in _subjects_mod.list_subjects()})
    except Exception:  # noqa: BLE001 — free text still works
        return []


# ── Places & capacity ─────────────────────────────────────────────

class PlacesPage:
    COLS = [("programme", "Programme", 220), ("places", "Places", 60),
            ("held", "Held", 50), ("left", "Left", 50),
            ("competing", "Competing", 75), ("apps", "Applications", 85),
            ("offers", "Offers waiting", 95), ("accepted", "Accepted", 70),
            ("enrolled", "Enrolled", 65), ("state", "", 120),
            ("notes", "Notes", 200)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, PLACES, "Places per programme",
            "A place is held at Offer Made, Offer Accepted, Deferred (into "
            "the cycle) or Enrolled. A programme with no places set is "
            "unlimited. Offers beyond the places set are refused unless "
            "capacity is overridden.")
        self.editable = pc.can(access.ADMISSIONS)
        st = "normal" if self.editable else "disabled"
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        self.cycle = pc.CyclePicker(bar, self.refresh)
        self.cycle.pack(side="left", padx=(0, 10))
        ttk.Button(bar, text="Set places…", command=self._set,
                   state=st).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Clear limit", command=self._clear,
                   state=st).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Ranking…", command=self._ranking,
                   state=st).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Export CSV…", command=self._export).pack(
            side="left", padx=(0, 4))
        self.limited = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Limited programmes only",
                        variable=self.limited, command=self.refresh).pack(
            side="left", padx=8)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=16)
        self.tree.tag_configure("full", background="#ffd6d6")
        self.tree.tag_configure("over", background="#fff1c6")
        self.tree.bind("<Double-1>", lambda _e: self._ranking())
        self._rows: dict[str, capacity.ProgrammePlaces] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        self._rows = {}
        cyc = self.cycle.get()
        if not cyc:
            self.status.set("Choose a cycle.")
            return
        ok, places = pc.load(self.status, PLACES, capacity.programme_places,
                             cyc, only_limited=self.limited.get())
        if not ok:
            return
        ok, offers = pc.load(self.status, PLACES, insights.offers_vs_capacity,
                             cyc)
        by_label = {r.programme.lower(): r for r in (offers or [])}
        full = over = 0
        for i, p in enumerate(places):
            o = by_label.get(p.label.lower())
            state, tag = "", ""
            if p.is_full:
                state, tag = "Full", "full"
                full += 1
            elif p.oversubscribed:
                state, tag = "Oversubscribed", "over"
                over += 1
            iid = str(i)
            self._rows[iid] = p
            self.tree.insert("", "end", iid=iid, tags=(tag,), values=(
                p.label, pc.fmt(p.places) or "no limit", p.held,
                pc.fmt(p.places_left), p.competing,
                o.applications if o else "", o.offers_made if o else "",
                o.accepted if o else "", o.enrolled if o else "", state,
                p.notes or ""))
        if ok:
            limited = sum(1 for p in places if p.places is not None)
            self.status.set(f"{cyc}: {len(places)} programme(s), {limited} "
                            f"with places set · {full} full · {over} "
                            "oversubscribed")

    def _selected(self) -> capacity.ProgrammePlaces | None:
        iid = pc.selected(self.tree, PLACES, quiet=True)
        return self._rows.get(iid) if iid else None

    def _set(self) -> None:
        cyc = self.cycle.get()
        if not cyc:
            messagebox.showinfo(PLACES, "Choose a cycle first.",
                                   parent=self.frame.winfo_toplevel())
            return
        p = self._selected()
        initial = {"qualification_type": p.qualification_type if p else
                   "A Level", "subject": p.subject if p else "",
                   "places": pc.fmt(p.places) if p else "",
                   "notes": (p.notes or "") if p else ""}

        def submit(v: dict[str, Any]) -> None:
            if v["places"] == "":
                raise ValueError("Enter the number of places (use Clear "
                                 "limit to remove one).")
            capacity.set_places(cyc, (v["qualification_type"], v["subject"]),
                                v["places"], notes=v["notes"] or None)

        if pc.ask_form(self.frame, f"Places — {cyc}", [
                ("qualification_type", "Qualification type", "combo",
                 programme_choices.programme_types()),
                ("subject", "Subject", "combo", _subjects()),
                ("places", "Places", "entry", None),
                ("notes", "Notes", "entry", None)], initial,
                on_submit=submit):
            self.refresh()

    def _clear(self) -> None:
        cyc = self.cycle.get()
        p = self._selected()
        if not cyc or p is None:
            messagebox.showinfo(PLACES, "Select a programme first.",
                                   parent=self.frame.winfo_toplevel())
            return
        if p.places is None:
            return
        if not messagebox.askyesno(
                PLACES, f"Remove the limit of {p.places} on {p.label} in "
                f"{cyc}? It becomes unlimited.",
                parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, PLACES, capacity.set_places, cyc,
                       (p.qualification_type, p.subject), None)
        if ok:
            self.refresh()

    def _ranking(self) -> None:
        cyc = self.cycle.get()
        p = self._selected()
        if not cyc or p is None:
            messagebox.showinfo(PLACES, "Select a programme first.",
                                   parent=self.frame.winfo_toplevel())
            return
        RankingDialog(self.frame, cyc, p)

    def _export(self) -> None:
        cyc = self.cycle.get()
        if not cyc:
            return
        ok, rows = pc.run(self.frame, PLACES, insights.offers_vs_capacity, cyc)
        if not ok:
            return
        text = insights.to_csv(rows)
        if not text:
            messagebox.showinfo(PLACES, "Nothing to export.",
                                parent=self.frame.winfo_toplevel())
            return
        pc.save_file(self.frame, text,
                     f"offers_vs_capacity_{cyc.replace('/', '-')}.csv")


class RankingDialog:
    COLS = [("pos", "#", 40), ("id", "ID", 85), ("name", "Name", 170),
            ("status", "Status", 120), ("submitted", "Submitted", 90),
            ("school", "Previous school", 170), ("held", "Holds place", 80),
            ("reasons", "Why this position", 380)]

    def __init__(self, parent: tk.Misc, cycle: str,
                 programme: capacity.ProgrammePlaces) -> None:
        self.cycle = cycle
        self.programme = programme
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title(f"Ranking — {programme.label} ({cycle})")
        self.win.geometry("1150x620")
        bar = ttk.Frame(self.win, padding=8)
        bar.pack(side="top", fill="x")
        left = ("no limit" if programme.places is None
                else f"{programme.places_left} of {programme.places} left")
        ttk.Label(bar, text=f"Places: {left}. Order: the enabled "
                  "oversubscription criteria by priority, then submission "
                  "date.").pack(side="left")
        self.holders = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Include those holding a place",
                        variable=self.holders, command=self.refresh).pack(
            side="right")
        foot = ttk.Frame(self.win, padding=8)
        foot.pack(side="bottom", fill="x")
        ttk.Button(foot, text="Export CSV…", command=self._export).pack(
            side="left")
        ttk.Button(foot, text="Close", command=self.win.destroy).pack(
            side="left", padx=6)
        holder = ttk.Frame(self.win, padding=(8, 0))
        holder.pack(fill="both", expand=True)
        self.tree = pc.make_tree(holder, self.COLS, height=18)
        self.tree.tag_configure("held", foreground="#777")
        self.rows: list[capacity.RankedApplicant] = []
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        p = self.programme
        ok, rows = pc.run(self.win, "Ranking", capacity.rank_applicants,
                          self.cycle, (p.qualification_type, p.subject),
                          include_holders=self.holders.get())
        self.rows = rows or []
        for r in self.rows:
            self.tree.insert("", "end", iid=r.applicant_id,
                             tags=("held",) if r.holds_place else (), values=(
                                 r.position, r.applicant_id, r.name, r.status,
                                 (r.submitted_at or "")[:10],
                                 r.previous_school or "",
                                 pc.yes(r.holds_place), r.reasons))

    def _export(self) -> None:
        text = insights.to_csv([{
            "position": r.position, "applicant_id": r.applicant_id,
            "name": r.name, "status": r.status,
            "submitted_at": r.submitted_at,
            "previous_school": r.previous_school,
            "holds_place": r.holds_place,
            "criteria_met": "; ".join(r.criteria_met)} for r in self.rows])
        if text:
            pc.save_file(self.win, text, "ranking.csv")


# ── Oversubscription criteria ─────────────────────────────────────

class CriteriaPage:
    COLS = [("priority", "Priority", 65), ("label", "Criterion", 300),
            ("enabled", "Applied", 70), ("available", "Available", 75),
            ("notes", "Notes", 420)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, CRITERIA, "Oversubscription criteria",
            "When a programme has more applicants than places, competing "
            "applicants are ranked by the applied criteria in this order; "
            "the submission date always breaks ties last.")
        self.editable = pc.can(access.ADMISSIONS)
        st = "normal" if self.editable else "disabled"
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        for text, cmd in (("Move up", lambda: self._move(-1)),
                          ("Move down", lambda: self._move(1)),
                          ("Apply", lambda: self._enable(True)),
                          ("Stop applying", lambda: self._enable(False))):
            ttk.Button(bar, text=text, command=cmd, state=st).pack(
                side="left", padx=(0, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=12)
        self.tree.tag_configure("off", foreground="#888")
        self.refresh()

    def refresh(self, keep: str | None = None) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, CRITERIA, capacity.list_criteria)
        if not ok:
            return
        self._keys = [c.key for c in rows]
        for c in rows:
            self.tree.insert("", "end", iid=c.key,
                             tags=() if c.enabled else ("off",), values=(
                                 c.priority, c.label, pc.yes(c.enabled),
                                 "Yes" if c.available else "No",
                                 c.notes or ""))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)
        on = sum(1 for c in rows if c.enabled)
        self.status.set(f"{on} of {len(rows)} criteria applied.")

    def _move(self, step: int) -> None:
        key = pc.selected(self.tree, CRITERIA)
        if not key:
            return
        keys = list(self._keys)
        i = keys.index(key)
        j = i + step
        if not 0 <= j < len(keys):
            return
        keys[i], keys[j] = keys[j], keys[i]
        ok, _ = pc.run(self.frame, CRITERIA, capacity.set_criteria_order, keys)
        if ok:
            self.refresh(keep=key)

    def _enable(self, on: bool) -> None:
        key = pc.selected(self.tree, CRITERIA)
        if not key:
            return
        ok, _ = pc.run(self.frame, CRITERIA, capacity.set_criterion_enabled,
                       key, on)
        if ok:
            self.refresh(keep=key)


# ── Feeder schools ────────────────────────────────────────────────

_FEEDER_FIELDS: list[pc.Field] = [
    ("name", "School name", "entry", None),
    ("urn", "URN", "entry", None),
    ("partner", "Partner school", "check", None),
    ("guaranteed_place_scheme", "In the guaranteed-place scheme", "check",
     None),
    ("notes", "Notes", "text", None),
]


class FeedersPage:
    COLS = [("name", "School", 260), ("urn", "URN", 80),
            ("partner", "Partner", 65), ("gps", "Guaranteed places", 115),
            ("active", "Active", 55), ("notes", "Notes", 360)]

    def __init__(self, nb: Any) -> None:
        self.frame = pc.new_page(
            nb, FEEDERS, "Feeder and partner schools",
            "Applicants from a school in the guaranteed-place scheme get the "
            "guaranteed-place flag when the rules are applied (a flag set by "
            "hand is never cleared). Removing a school keeps it in the "
            "history as inactive.")
        self.editable = pc.can(access.ADMISSIONS)
        st = "normal" if self.editable else "disabled"
        bar = ttk.Frame(self.frame)
        bar.pack(side="top", fill="x", pady=(0, 4))
        for text, cmd in (("Add school…", self._add), ("Edit…", self._edit),
                          ("Remove", self._remove),
                          ("Reactivate", self._reactivate)):
            ttk.Button(bar, text=text, command=cmd, state=st).pack(
                side="left", padx=(0, 4))
        self.inactive = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show inactive", variable=self.inactive,
                        command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(
            side="right")
        bar2 = ttk.Frame(self.frame)
        bar2.pack(side="top", fill="x", pady=(0, 4))
        self.cycle = pc.CyclePicker(bar2, lambda: None,
                                    label="Apply the scheme to cycle:")
        self.cycle.pack(side="left")
        ttk.Button(bar2, text="Apply feeder rules", command=self._apply,
                   state=st).pack(side="left", padx=6)
        self.status = pc.status_line(self.frame)
        self.tree = pc.make_tree(self.frame, self.COLS, height=16)
        self.tree.tag_configure("inactive", foreground="#888")
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        self._rows: dict[str, capacity.FeederSchool] = {}
        self.refresh()

    def refresh(self) -> None:
        pc.clear(self.tree)
        ok, rows = pc.load(self.status, FEEDERS, capacity.list_feeder_schools,
                           include_inactive=self.inactive.get())
        if not ok:
            return
        self._rows = {str(f.school_id): f for f in rows}
        for f in rows:
            self.tree.insert("", "end", iid=str(f.school_id),
                             tags=() if f.active else ("inactive",), values=(
                                 f.name, f.urn or "", pc.yes(f.partner),
                                 pc.yes(f.guaranteed_place_scheme),
                                 "Yes" if f.active else "No",
                                 (f.notes or "").replace("\n", " ")))
        gps = sum(1 for f in rows if f.guaranteed_place_scheme and f.active)
        self.status.set(f"{len(rows)} school(s) · {gps} in the "
                        "guaranteed-place scheme")

    def _school(self) -> capacity.FeederSchool | None:
        iid = pc.selected(self.tree, FEEDERS)
        return self._rows.get(iid) if iid else None

    def _add(self) -> None:
        def submit(v: dict[str, Any]) -> None:
            capacity.add_feeder_school(
                v["name"], partner=v["partner"],
                guaranteed_place_scheme=v["guaranteed_place_scheme"],
                urn=v["urn"] or None, notes=v["notes"] or None)

        if pc.ask_form(self.frame, "Add feeder school", _FEEDER_FIELDS,
                       {"partner": True}, on_submit=submit):
            self.refresh()

    def _edit(self) -> None:
        f = self._school()
        if f is None:
            return
        initial = {"name": f.name, "urn": f.urn, "partner": f.partner,
                   "guaranteed_place_scheme": f.guaranteed_place_scheme,
                   "notes": f.notes}
        if pc.ask_form(self.frame, f"Edit {f.name}", _FEEDER_FIELDS, initial,
                       on_submit=lambda v: capacity.update_feeder_school(
                           f.school_id, **v)):
            self.refresh()

    def _remove(self) -> None:
        f = self._school()
        if f is None or not f.active:
            return
        if not messagebox.askyesno(
                FEEDERS, f"Remove {f.name} from the feeder schools? It is kept "
                "as inactive; applicants' history keeps the name.",
                parent=self.frame.winfo_toplevel()):
            return
        ok, _ = pc.run(self.frame, FEEDERS, capacity.remove_feeder_school,
                       f.school_id)
        if ok:
            self.refresh()

    def _reactivate(self) -> None:
        f = self._school()
        if f is None or f.active:
            return
        ok, _ = pc.run(self.frame, FEEDERS, capacity.update_feeder_school,
                       f.school_id, active=True)
        if ok:
            self.refresh()

    def _apply(self) -> None:
        cyc = self.cycle.get()
        if not cyc:
            return
        if not messagebox.askyesno(
                FEEDERS, f"Give every open application in {cyc} from a "
                "guaranteed-place scheme school the guaranteed-place flag?",
                parent=self.frame.winfo_toplevel()):
            return
        ok, ids = pc.run(self.frame, FEEDERS, capacity.apply_feeder_rules_all,
                         cyc)
        if not ok:
            return
        msg = (f"{len(ids)} applicant(s) given a guaranteed place:\n"
               + ", ".join(ids)) if ids else (
            f"No open application in {cyc} needed the flag.")
        messagebox.showinfo(FEEDERS, msg, parent=self.frame.winfo_toplevel())
