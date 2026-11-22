"""Results Day tab and the structured offer-conditions editor (UCAS window).

* :class:`ResultsDayTab` — every firm / insurance applicant holding a
  conditional offer, with the verdict against their conditions, the
  results (embargoed ones marked), and the actions: confirm, decline,
  auto-confirm, and "Release held confirmations". Actions on an applicant
  whose results are still embargoed are held, and listed with who held
  them and when.
* ``ConditionsEditor`` — the rows behind an offer's grade requirement
  ("ABB including B in Mathematics" as a profile row plus a subject row),
  embedded in the applicant decision dialog. Shared with the sixth form, so
  it lives in ``platform/delivery/gui/offer_conditions_editor`` and is
  re-exported here.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from education_system.platform.cross_system import offer_conditions as oc
from education_system.platform.delivery.gui.offer_conditions_editor import (  # noqa: F401
    ConditionsEditor,
)

logger = logging.getLogger(__name__)

_VERDICT_TAGS = {
    oc.MET: ("#e6f7e6", "#0d6b2a"),
    oc.MISSED: ("#ffd1d1", "#8c0d0d"),
    oc.REVIEW: ("#fff7e6", "#7a5800"),
    oc.PENDING: ("#eeeeee", "#555555"),
}


def _rd():
    from education_system.systems.university.domains.admissions.domain.ucas import (
        results_day,
    )
    return results_day


def _officer(widget) -> str | None:
    try:
        cu = getattr(getattr(widget, "auth", None), "current_user", None)
        if isinstance(cu, dict) and cu.get("username"):
            return cu["username"]
    except Exception:
        pass
    try:
        from education_system.systems.university.infrastructure.auth.core_utils.global_auth import (
            get_current_username,
        )
        return get_current_username() or None
    except Exception:
        logger.debug("Could not resolve the current user", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────
# Results day tab
# ─────────────────────────────────────────────────────────────────

class ResultsDayTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb, padding=8)
        nb.add(self.frame, text="Results Day")
        self._candidates: dict[str, Any] = {}
        self._built = False
        nb.bind("<<NotebookTabChanged>>", self._on_tab, add="+")
        self._nb = nb

    def _on_tab(self, _e=None) -> None:
        try:
            if self._nb.select() == str(self.frame) and not self._built:
                self._build()
                self.refresh()
        except Exception:
            logger.exception("Results Day tab failed to open")

    def _build(self) -> None:
        self._built = True
        top = ttk.Frame(self.frame)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Cycle year:").pack(side="left")
        self.e_year = ttk.Entry(top, width=8)
        self.e_year.pack(side="left", padx=(4, 12))
        self.insurance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Include insurance",
                        variable=self.insurance_var).pack(side="left", padx=(0, 12))
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        self.summary = ttk.Label(top, text="", foreground="#555")
        self.summary.pack(side="left", padx=(12, 0))

        # Action bars are packed before the expanding tables.
        actions = ttk.Frame(self.frame)
        actions.pack(side="bottom", fill="x", pady=(6, 0))
        for label, cmd in (("Confirm place", self._confirm),
                           ("Decline place", self._decline),
                           ("Auto-confirm met (preview)", self._auto_confirm),
                           ("Release held confirmations", self._release),
                           ("Cancel selected hold", self._cancel_hold)):
            ttk.Button(actions, text=label, command=cmd).pack(side="left", padx=(0, 6))

        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True)
        upper = ttk.Frame(pane)
        lower = ttk.LabelFrame(pane, text="Held until results publication / history",
                               padding=4)
        pane.add(upper, weight=3)
        pane.add(lower, weight=1)

        cols = (("student", "Student", 160), ("course", "Course", 170),
                ("final", "Reply", 70), ("conditions", "Conditions", 220),
                ("achieved", "Results", 240), ("verdict", "Verdict", 70),
                ("status", "Status", 200), ("reason", "Why", 320))
        self.tree = ttk.Treeview(upper, columns=[c[0] for c in cols],
                                 show="headings", height=14)
        for key, label, width in cols:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        for verdict, (bg, fg) in _VERDICT_TAGS.items():
            self.tree.tag_configure(verdict, background=bg, foreground=fg)
        vs = ttk.Scrollbar(upper, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        hcols = (("id", "#", 40), ("choice", "Choice", 60), ("action", "Action", 70),
                 ("status", "Status", 80), ("release_at", "Results out", 130),
                 ("held", "Held by / at", 200), ("released", "Released by / at", 220),
                 ("outcome", "Outcome", 320))
        self.holds = ttk.Treeview(lower, columns=[c[0] for c in hcols],
                                  show="headings", height=5)
        for key, label, width in hcols:
            self.holds.heading(key, text=label)
            self.holds.column(key, width=width, anchor="w")
        self.holds.pack(fill="both", expand=True)

    def _year(self) -> int | None:
        raw = self.e_year.get().strip()
        return int(raw) if raw.isdigit() else None

    def refresh(self) -> None:
        if not self._built:
            return
        rd = _rd()
        try:
            rows = rd.board(cycle_year=self._year(),
                            include_insurance=self.insurance_var.get(),
                            acting_user=_officer(self.root))
        except Exception as e:
            logger.exception("Results-day board failed")
            messagebox.showerror("Results Day", f"Could not load the board: {e}",
                                 parent=self.root)
            return
        self.tree.delete(*self.tree.get_children())
        self._candidates = {}
        for c in rows:
            iid = str(c.choice_id)
            self._candidates[iid] = c
            self.tree.insert("", "end", iid=iid, tags=(c.verdict,), values=(
                f"{c.student_name} ({c.student_id})",
                c.course_name + (f" ({c.course_code})" if c.course_code else ""),
                c.final_decision or "—", c.conditions_label, c.achieved_label,
                c.verdict, c.status_label or "—", c.reason))
        counts = {}
        for c in rows:
            counts[c.verdict] = counts.get(c.verdict, 0) + 1
        held = sum(1 for c in rows if c.hold is not None)
        self.summary.configure(text=(
            ", ".join(f"{v}: {n}" for v, n in counts.items()) or "No applicants")
            + (f" — {held} held until results publication" if held else ""))
        self.holds.delete(*self.holds.get_children())
        for h in rd.list_holds()[:200]:
            self.holds.insert("", "end", iid=f"h{h.hold_id}", values=(
                h.hold_id, h.sf_choice_id,
                h.action + (" (auto)" if h.automatic else ""), h.status,
                h.release_at or "—", f"{h.held_by or '—'} / {h.held_at}",
                f"{h.released_by or '—'} / {h.released_at or '—'}",
                h.outcome or h.reason or ""))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Results Day", "Pick an applicant first.",
                                parent=self.root)
            return None
        return self._candidates.get(sel[0])

    def _report(self, out, what: str) -> None:
        rd = _rd()
        if isinstance(out, rd.Hold):
            messagebox.showinfo(
                "Results Day",
                f"{what} held until results publication"
                + (f" ({out.release_at})" if out.release_at else "")
                + ". Nothing has been sent; it will be applied when the "
                  "results are out.", parent=self.root)
        else:
            messagebox.showinfo("Results Day", f"{what} recorded.", parent=self.root)

    def _confirm(self) -> None:
        c = self._selected()
        if c is None:
            return
        if c.verdict != oc.MET and not messagebox.askyesno(
                "Confirm place",
                f"The verdict is {c.verdict}: {c.reason}\n\nConfirm anyway?",
                parent=self.root):
            return
        try:
            out = _rd().confirm_place(c.choice_id, decided_by=_officer(self.root),
                                      note=c.reason)
        except Exception as e:
            logger.exception("confirm_place failed")
            messagebox.showerror("Results Day", str(e), parent=self.root)
            return
        self._report(out, "Confirmation")
        self.refresh()

    def _decline(self) -> None:
        c = self._selected()
        if c is None:
            return
        reason = simpledialog.askstring(
            "Decline place", "Reason (sent to the applicant):",
            initialvalue="Conditions of the offer were not met.", parent=self.root)
        if reason is None:
            return
        try:
            out = _rd().decline_place(c.choice_id, decided_by=_officer(self.root),
                                      reason=reason)
        except Exception as e:
            logger.exception("decline_place failed")
            messagebox.showerror("Results Day", str(e), parent=self.root)
            return
        self._report(out, "Decline")
        self.refresh()

    def _auto_confirm(self) -> None:
        rd = _rd()
        try:
            would = rd.auto_confirm(cycle_year=self._year(), dry_run=True)
        except Exception as e:
            logger.exception("auto_confirm preview failed")
            messagebox.showerror("Results Day", str(e), parent=self.root)
            return
        if not would:
            messagebox.showinfo("Results Day", "No firm applicant has met "
                                "their conditions in full.", parent=self.root)
            return
        later = sum(1 for c in would if c.is_embargoed)
        names = "\n".join(f"  {c.student_name} — {c.course_name}"
                          + ("  (held until results publication)" if c.is_embargoed else "")
                          for c in would[:25])
        if not messagebox.askyesno(
                "Auto-confirm",
                f"{len(would)} place(s) meet their conditions"
                + (f"; {later} will be held until results are published" if later else "")
                + f":\n\n{names}\n\nConfirm them now?", parent=self.root):
            return
        done = rd.auto_confirm(cycle_year=self._year(), dry_run=False,
                               decided_by=_officer(self.root))
        messagebox.showinfo("Results Day", f"{len(done)} confirmed or held.",
                            parent=self.root)
        self.refresh()

    def _release(self) -> None:
        try:
            counts = _rd().release_held(released_by=_officer(self.root))
        except Exception as e:
            logger.exception("release_held failed")
            messagebox.showerror("Results Day", str(e), parent=self.root)
            return
        messagebox.showinfo(
            "Release held confirmations",
            f"Applied: {counts['Applied']}   Lapsed: {counts['Lapsed']}   "
            f"Failed: {counts['Failed']}\nStill embargoed (left held): "
            f"{counts['waiting']}", parent=self.root)
        self.refresh()

    def _cancel_hold(self) -> None:
        sel = self.holds.selection()
        if not sel:
            messagebox.showinfo("Results Day", "Pick a hold in the lower list.",
                                parent=self.root)
            return
        hold_id = int(sel[0][1:])
        if not messagebox.askyesno("Cancel hold",
                                   f"Cancel held action #{hold_id}?", parent=self.root):
            return
        if not _rd().cancel_hold(hold_id, cancelled_by=_officer(self.root)):
            messagebox.showinfo("Results Day", "That hold is no longer held.",
                                parent=self.root)
        self.refresh()
