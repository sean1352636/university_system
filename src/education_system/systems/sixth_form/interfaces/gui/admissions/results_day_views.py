"""Results Day tab: evaluate conditional offers and decide."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    gcse_results_day as rd,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    applicant_actions as act,
)

logger = logging.getLogger(__name__)


class ResultsDayTab:
    """Results-day dashboard: outcomes, decisions and the worklist."""

    COLS = [("id", "ID", 90), ("name", "Name", 190), ("status", "Status", 110),
            ("outcome", "Outcome", 90), ("decision", "Decision", 150),
            ("detail", "Conditions", 420), ("by", "Decided by", 100)]

    LIVE_COLS = [("id", "ID", 90), ("name", "Name", 190),
                 ("status", "Status", 110), ("intake", "Intake", 70),
                 ("expiry", "Offer expiry", 95),
                 ("conditions", "Conditions", 520)]

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Results Day")
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(top, text="Entry year:").pack(side="left")
        self.cycle = ttk.Entry(top, width=10)
        self.cycle.insert(0, rd.current_cycle())
        self.cycle.pack(side="left", padx=(4, 12))
        ttk.Button(top, text="Evaluate all offers",
                   command=self._evaluate_all).pack(side="left")
        ttk.Button(top, text="Import actual results CSV…",
                   command=self._import).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")
        self.cards = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.cards,
                  font=("", 11, "bold")).pack(fill="x", padx=8, pady=4)
        acts = ttk.Frame(self.frame)
        acts.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(acts, text="Results & conditions…",
                   command=self._gcses).pack(side="left")
        ttk.Button(acts, text="Re-evaluate",
                   command=self._evaluate_one).pack(side="left", padx=4)
        ttk.Button(acts, text="Confirm place",
                   command=self._confirm).pack(side="left", padx=(12, 4))
        ttk.Button(acts, text="Confirm near miss",
                   command=lambda: self._confirm(near=True)).pack(side="left")
        ttk.Button(acts, text="Offer alternative…",
                   command=self._alternative).pack(side="left", padx=4)
        ttk.Button(acts, text="Decline",
                   command=self._decline).pack(side="left")
        ttk.Button(acts, text="Reset decision",
                   command=self._reset).pack(side="left", padx=(12, 0))
        self.f_outcome = ttk.Combobox(
            acts, state="readonly", width=12,
            values=("", "Met", "Near miss", "Not met", "Pending"))
        self.f_outcome.pack(side="right")
        self.f_outcome.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(acts, text="Show outcome:").pack(side="right", padx=4)
        # Live conditional offers (packed before the main table so it is
        # never squeezed off a short screen).
        live = ttk.LabelFrame(self.frame, text="Live conditional offers")
        live.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.live_var = tk.StringVar()
        lbar = ttk.Frame(live)
        lbar.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(lbar, textvariable=self.live_var, foreground="#555").pack(
            side="left")
        ttk.Button(lbar, text="Results & conditions…",
                   command=self._live_gcses).pack(side="right")
        lholder = ttk.Frame(live)
        lholder.pack(fill="x", padx=4, pady=4)
        self.live = ui.make_tree(lholder, self.LIVE_COLS, height=6)
        self.live.bind("<Double-1>", lambda _e: self._live_gcses())
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ui.make_tree(holder, self.COLS, height=14)
        for tag, colour in (("Met", "#d8f4d8"), ("Near miss", "#fff2c4"),
                            ("Not met", "#ffd6d6")):
            self.tree.tag_configure(tag, background=colour)
        self.tree.bind("<Double-1>", lambda _e: self._gcses())
        self.refresh()

    def _cyc(self) -> str:
        return self.cycle.get().strip() or rd.current_cycle()

    def _refresh_live(self) -> None:
        ui.clear(self.live)
        try:
            rows = rd.conditional_applicants(intake_year=self._cyc())
        except Exception as e:  # noqa: BLE001 — shown in the panel
            logger.exception("Live conditional offers failed")
            self.live_var.set(f"Error: {act.describe(e)}")
            return
        self.live_var.set(f"{len(rows)} applicant(s) holding a conditional "
                          f"offer for {self._cyc()}")
        for a in rows:
            self.live.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name, a.status, a.intake_year or "",
                a.offer_expiry or "", a.offer_conditions or ""))

    def _live_gcses(self) -> None:
        aid = ui.require_iid(self.live, "Live conditional offers")
        if aid:
            from education_system.systems.sixth_form.interfaces.gui.admissions.entry_requirements_views import (
                open_applicant_gcses,
            )
            open_applicant_gcses(self.frame, aid, on_change=self.refresh)

    def refresh(self) -> None:
        ui.clear(self.tree)
        self._refresh_live()
        try:
            d = rd.dashboard(cycle=self._cyc())
        except Exception as e:  # noqa: BLE001
            logger.exception("Results day dashboard failed")
            self.cards.set(f"Error: {e}")
            return
        o = d.by_outcome
        self.cards.set(
            f"{d.total} offer(s) · Met {o.get('Met', 0)} · Near miss "
            f"{o.get('Near miss', 0)} · Not met {o.get('Not met', 0)} · "
            f"Pending {o.get('Pending', 0)}   |   awaiting results "
            f"{d.awaiting_results} · awaiting decision {d.awaiting_decision}"
            f" · confirmed {d.by_decision.get('Confirmed', 0) + d.by_decision.get('Confirmed (near miss)', 0)}"
            f" · alternatives {d.by_decision.get('Alternative offered', 0)}"
            f" · declined {d.by_decision.get('Declined', 0)}")
        want = self.f_outcome.get()
        for r in d.rows:
            if want and r.outcome != want:
                continue
            self.tree.insert("", "end", iid=r.applicant_id, values=(
                r.applicant_id, r.applicant_name, r.status, r.outcome,
                r.decision + (f" — {r.alternative}" if r.alternative else ""),
                r.outcome_detail or r.conditions, r.decided_by or ""),
                tags=(r.outcome,))

    def _sel(self) -> str | None:
        return ui.require_iid(self.tree, "Results day")

    def _run(self, fn, *args, **kw) -> None:
        act.attempt(self.frame, "Results day", fn, *args, **kw)
        self.refresh()

    def _evaluate_all(self) -> None:
        ok, counts = act.attempt(self.frame, "Results day", rd.evaluate_all,
                                 cycle=self._cyc())
        if not ok:
            return
        messagebox.showinfo("Results day", "Evaluated: " + (", ".join(
            f"{k} {v}" for k, v in counts.items()) or "no live offers"),
            parent=self.frame)
        self.refresh()

    def _evaluate_one(self) -> None:
        aid = self._sel()
        if aid:
            self._run(rd.evaluate_applicant, aid, cycle=self._cyc())

    def _import(self) -> None:
        from education_system.systems.sixth_form.interfaces.gui.admissions.entry_requirements_views import (
            import_results_csv,
        )
        import_results_csv(self.frame)
        self.refresh()

    def _gcses(self) -> None:
        aid = self._sel()
        if aid:
            from education_system.systems.sixth_form.interfaces.gui.admissions.entry_requirements_views import (
                open_applicant_gcses,
            )
            open_applicant_gcses(self.frame, aid, on_change=self.refresh)

    def _notes(self, title: str) -> str | None:
        v = ui.ask_form(self.frame, title, [("notes", "Notes", "text", None)])
        return None if v is None else v["notes"]

    def _confirm(self, near: bool = False) -> None:
        aid = self._sel()
        if not aid:
            return
        notes = self._notes("Confirm place")
        if notes is None:
            return
        self._run(rd.confirm, aid, by=ui.current_username(), notes=notes,
                  allow_near_miss=near, cycle=self._cyc())

    def _decline(self) -> None:
        aid = self._sel()
        if not aid or not messagebox.askyesno(
                "Decline", f"Withdraw the offer to {aid} (conditions not "
                "met)?", parent=self.frame):
            return
        notes = self._notes("Decline")
        if notes is None:
            return
        self._run(rd.decline, aid, by=ui.current_username(), notes=notes,
                  cycle=self._cyc())

    def _alternative(self) -> None:
        aid = self._sel()
        if not aid:
            return
        current = "; ".join(f"{c.qualification_type}: {c.subject}"
                            for c in adm.list_programme_choices(aid))
        v = ui.ask_form(self.frame, "Offer alternative", [
            ("choices", "New programme (Type: Subject; …)", "text", None),
            ("notes", "Notes", "text", None)], {"choices": current})
        if v is None:
            return
        try:
            choices = parse_choices_text(v["choices"])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Offer alternative", str(e), parent=self.frame)
            return
        self._run(rd.offer_alternative, aid, choices=choices,
                  by=ui.current_username(), notes=v["notes"],
                  cycle=self._cyc())

    def _reset(self) -> None:
        aid = self._sel()
        if aid:
            self._run(rd.reset_decision, aid, cycle=self._cyc())


def parse_choices_text(text: str) -> list[dict]:
    """"A Level: Biology; BTEC Diploma: Sport" -> choice dicts.

    A part without a type is read as an A Level.
    """
    out = []
    for part in (text or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            q, s = part.split(":", 1)
            out.append({"qualification_type": q.strip(), "subject": s.strip()})
        else:
            out.append({"qualification_type": "A Level", "subject": part})
    if not out:
        raise adm.ValidationError("Enter at least one choice")
    return out


def open_results_day_window(parent=None) -> None:
    win = ui.new_window(parent, "GCSE results day")
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    ResultsDayTab(nb)
