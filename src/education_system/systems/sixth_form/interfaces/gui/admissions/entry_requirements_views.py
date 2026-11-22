"""Entry requirements tab and the per-applicant GCSEs & conditions dialog."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    entry_requirements as er,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

from . import applicant_actions as act

logger = logging.getLogger(__name__)


def _programme_options() -> list[str]:
    names = [er.GENERAL_PROGRAMME]
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names += [s.name for s in _subjects.list_subjects()]
    except Exception:
        pass
    names += [p for p in er.programmes_without_requirements() if p not in names]
    return names


def _parse_minimums(text: str) -> dict[str, str]:
    """"Mathematics=7; English=4" -> {"Mathematics": "7", "English": "4"}."""
    out: dict[str, str] = {}
    for part in (text or "").replace("\n", ";").split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise er.ValidationError(
                f"'{part.strip()}' — write subject minimums as Subject=grade")
        subj, grade = part.split("=", 1)
        out[subj.strip()] = grade.strip()
    return out


class EntryRequirementsTab:
    """Entry requirements per programme (subject / course name)."""

    COLS = [("programme", "Programme", 220), ("count", "GCSEs", 70),
            ("grade", "At grade", 70), ("avg", "Avg points", 80),
            ("subjects", "Subject minimums", 300), ("by", "Updated by", 110),
            ("at", "Updated", 140)]

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Entry Requirements")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="New…", command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit…", command=self._edit).pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Delete", command=self._delete).pack(side="left")
        ttk.Button(bar, text="Without requirements…",
                   command=self._missing).pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right")
        ttk.Label(self.frame, foreground="#555", text=(
            f"'{er.GENERAL_PROGRAMME}' applies to every applicant; a "
            "programme's own rules are added for applicants who choose it. "
            "Grades are 9-1 numbers.")).pack(fill="x", padx=8)
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, self.COLS)
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            rows = er.list_requirements()
        except Exception as e:  # noqa: BLE001
            logger.exception("Could not load entry requirements")
            messagebox.showerror("Entry requirements", str(e),
                                 parent=self.frame)
            return
        for r in rows:
            self.tree.insert("", "end", iid=r.programme, values=(
                r.programme, r.min_gcse_count or "",
                r.min_gcse_grade or "",
                f"{r.min_average_points:g}" if r.min_average_points else "",
                "; ".join(f"{s} {g}" for s, g in r.subject_minimums.items()),
                r.updated_by or "", r.updated_at or ""))

    def _form(self, existing: er.Requirement | None) -> None:
        initial = {}
        if existing:
            initial = {
                "programme": existing.programme,
                "count": existing.min_gcse_count or "",
                "grade": existing.min_gcse_grade or "",
                "avg": existing.min_average_points or "",
                "subjects": "; ".join(f"{s}={g}" for s, g in
                                      existing.subject_minimums.items()),
                "notes": existing.notes or "",
            }

        def save(v: dict) -> None:
            if existing and v["programme"] != existing.programme:
                er.delete_requirement(existing.programme)
            er.set_requirement(
                v["programme"], min_gcse_count=v["count"],
                min_gcse_grade=v["grade"], min_average_points=v["avg"],
                subject_minimums=_parse_minimums(v["subjects"]),
                notes=v["notes"], updated_by=ui.current_username())

        if ui.ask_form(self.frame, "Entry requirement", [
                ("programme", "Programme (subject / course)", "combo",
                 _programme_options()),
                ("count", "Minimum number of GCSEs", "entry", None),
                ("grade", "…at grade (9-1)", "entry", None),
                ("avg", "Minimum average point score", "entry", None),
                ("subjects", "Subject minimums (Subject=grade; …)", "entry",
                 None),
                ("notes", "Notes", "text", None)],
                initial, on_submit=save) is not None:
            self.refresh()

    def _new(self) -> None:
        self._form(None)

    def _edit(self) -> None:
        iid = ui.require_iid(self.tree, "Entry requirements")
        if iid:
            self._form(er.get_requirement(iid))

    def _delete(self) -> None:
        iid = ui.require_iid(self.tree, "Entry requirements")
        if iid and messagebox.askyesno("Entry requirements",
                                       f"Delete the requirement for {iid}?",
                                       parent=self.frame):
            ok, _ = act.attempt(self.frame, "Entry requirements",
                                er.delete_requirement, iid)
            if ok:
                self.refresh()

    def _missing(self) -> None:
        rows = er.programmes_without_requirements()
        ui.show_text(self.frame, "Programmes without requirements",
                     "Chosen by open applicants but with no entry "
                     "requirement:\n\n" + ("\n".join(rows) or "(none)"))


class ApplicantGcseDialog:
    """An applicant's GCSE results and structured offer conditions."""

    def __init__(self, parent: tk.Misc, applicant_id: str,
                 on_change=None) -> None:
        self.aid = applicant_id
        self.on_change = on_change
        a = adm.get_applicant(applicant_id)
        self.win = ui.new_window(parent, f"GCSEs & conditions — "
                                 f"{applicant_id} "
                                 f"{a.full_name if a else ''}",
                                 geometry="1200x800", minsize=(1000, 700))
        self.summary = tk.StringVar()
        ttk.Label(self.win, textvariable=self.summary,
                  font=("", 11, "bold")).pack(fill="x", padx=10, pady=(8, 0))

        g = ttk.LabelFrame(self.win, text="GCSE results")
        g.pack(fill="both", expand=True, padx=10, pady=6)
        gbar = ttk.Frame(g)
        gbar.pack(fill="x", pady=(4, 4))
        ttk.Button(gbar, text="Add / replace…",
                   command=self._add_gcse).pack(side="left")
        ttk.Button(gbar, text="Delete",
                   command=self._del_gcse).pack(side="left", padx=4)
        ttk.Button(gbar, text="Read predicted text",
                   command=self._from_text).pack(side="left", padx=4)
        ttk.Button(gbar, text="Import results CSV…",
                   command=self._import_csv).pack(side="left", padx=4)
        self.gtree = ui.make_tree(g, [
            ("type", "Type", 80), ("subject", "Subject", 200),
            ("grade", "Grade", 60), ("kind", "Kind", 110),
            ("year", "Year", 60), ("board", "Board", 100),
            ("source", "Source", 100), ("by", "Entered by", 110)], height=8)

        c = ttk.LabelFrame(self.win, text="Offer conditions")
        c.pack(fill="both", expand=True, padx=10, pady=6)
        cbar = ttk.Frame(c)
        cbar.pack(fill="x", pady=(4, 4))
        ttk.Button(cbar, text="Generate from entry requirements",
                   command=self._generate).pack(side="left")
        ttk.Button(cbar, text="Add…", command=self._add_cond).pack(
            side="left", padx=4)
        ttk.Button(cbar, text="Edit…", command=self._edit_cond).pack(
            side="left")
        ttk.Button(cbar, text="Delete", command=self._del_cond).pack(
            side="left", padx=4)
        ttk.Button(cbar, text="Set outcome…",
                   command=self._manual).pack(side="left")
        ttk.Button(cbar, text="Evaluate (predicted)",
                   command=lambda: self._evaluate("Predicted")).pack(
            side="left", padx=(12, 4))
        ttk.Button(cbar, text="Evaluate (actual)",
                   command=lambda: self._evaluate("Actual")).pack(side="left")
        self.ctree = ui.make_tree(c, [
            ("desc", "Condition", 320), ("kind", "Kind", 110),
            ("from", "From", 150), ("outcome", "Outcome", 90),
            ("manual", "Staff", 80), ("detail", "Detail", 300)], height=8)
        self.ctree.tag_configure("Met", background="#d8f4d8")
        self.ctree.tag_configure("Near miss", background="#fff2c4")
        self.ctree.tag_configure("Not met", background="#ffd6d6")
        self.refresh()

    def _changed(self) -> None:
        self.refresh()
        if self.on_change:
            self.on_change()

    def refresh(self) -> None:
        ui.clear(self.gtree)
        for x in er.list_gcses(self.aid):
            self.gtree.insert("", "end", iid=str(x.id), values=(
                x.result_type, x.subject, x.grade, x.kind, x.year or "",
                x.exam_board or "", x.source, x.entered_by or ""))
        ui.clear(self.ctree)
        for x in er.list_conditions(self.aid):
            self.ctree.insert("", "end", iid=str(x.condition_id), values=(
                x.description, x.kind, x.source_programme or "", x.outcome,
                x.manual_outcome or "", x.outcome_detail or ""),
                tags=(x.effective_outcome,))
        a = adm.get_applicant(self.aid)
        actual = len(er.list_gcses(self.aid, result_type="Actual"))
        self.summary.set(
            f"{a.full_name if a else self.aid} — offer: "
            f"{(a.offer_type if a else None) or 'none'} · "
            f"{actual} actual result(s) · conditions text: "
            f"{(a.offer_conditions if a else None) or '—'}")

    # GCSEs
    def _add_gcse(self) -> None:
        def save(v: dict) -> None:
            er.record_gcse(self.aid, v["subject"], v["grade"],
                           result_type=v["type"] or "Actual",
                           kind=v["kind"] or "GCSE", year=v["year"] or None,
                           exam_board=v["board"] or None,
                           entered_by=ui.current_username())
        if ui.ask_form(self.win, "GCSE result", [
                ("type", "Result type", "readonly", er.RESULT_TYPES),
                ("subject", "Subject", "entry", None),
                ("grade", "Grade (9-1 or A*-G)", "combo",
                 er.GCSE_91_GRADES + er.LEGACY_GRADES),
                ("kind", "Kind", "readonly", er.GCSE_KINDS),
                ("year", "Year", "entry", None),
                ("board", "Exam board", "entry", None)],
                {"type": "Actual", "kind": "GCSE"}, on_submit=save):
            self._changed()

    def _del_gcse(self) -> None:
        iid = ui.require_iid(self.gtree, "GCSE results")
        if iid and messagebox.askyesno("GCSE results", "Delete this result?",
                                       parent=self.win):
            ok, _ = act.attempt(self.win, "GCSE results", er.delete_gcse,
                                int(iid))
            if ok:
                self._changed()

    def _from_text(self) -> None:
        try:
            n, unread = er.import_predicted_from_text(
                self.aid, entered_by=ui.current_username())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Predicted GCSEs", str(e), parent=self.win)
            return
        msg = f"{n} predicted result(s) recorded."
        if unread:
            msg += "\n\nCould not read:\n" + "\n".join(unread)
        messagebox.showinfo("Predicted GCSEs", msg, parent=self.win)
        self._changed()

    def _import_csv(self) -> None:
        import_results_csv(self.win)
        self._changed()

    # Conditions
    def _generate(self) -> None:
        if er.list_conditions(self.aid) and not messagebox.askyesno(
                "Offer conditions", "Replace the generated conditions "
                "(hand-added ones are kept)?", parent=self.win):
            return
        ok, rows = act.attempt(self.win, "Offer conditions",
                               er.generate_conditions, self.aid)
        if not ok:
            return
        if not rows:
            messagebox.showinfo("Offer conditions", "No entry requirements "
                                "apply to this applicant's choices.",
                                parent=self.win)
        self._changed()

    def _cond_form(self, existing: er.OfferCondition | None) -> None:
        initial = {"kind": "other"}
        if existing:
            initial = {"kind": existing.kind, "subject": existing.subject,
                       "grade": existing.min_grade, "count": existing.min_count,
                       "points": existing.min_points,
                       "desc": existing.description}

        def save(v: dict) -> None:
            args = dict(kind=v["kind"], description=v["desc"] or None,
                        subject=v["subject"] or None,
                        min_grade=v["grade"] or None,
                        min_count=v["count"] or None,
                        min_points=v["points"] or None)
            if existing:
                er.update_condition(existing.condition_id, **args)
            else:
                er.add_condition(self.aid, **args)

        if ui.ask_form(self.win, "Offer condition", [
                ("kind", "Kind", "readonly", er.CONDITION_KINDS),
                ("subject", "GCSE subject (subject_grade)", "entry", None),
                ("grade", "Grade 9-1 (subject_grade / gcse_count)", "entry",
                 None),
                ("count", "Number of GCSEs (gcse_count)", "entry", None),
                ("points", "Average points (average_points)", "entry", None),
                ("desc", "Wording (blank = automatic)", "text", None)],
                initial, on_submit=save):
            self._changed()

    def _add_cond(self) -> None:
        self._cond_form(None)

    def _edit_cond(self) -> None:
        iid = ui.require_iid(self.ctree, "Offer conditions")
        if iid:
            self._cond_form(er.get_condition(int(iid)))

    def _del_cond(self) -> None:
        iid = ui.require_iid(self.ctree, "Offer conditions")
        if iid and messagebox.askyesno("Offer conditions",
                                       "Delete this condition?",
                                       parent=self.win):
            ok, _ = act.attempt(self.win, "Offer conditions",
                                er.delete_condition, int(iid))
            if ok:
                self._changed()

    def _manual(self) -> None:
        iid = ui.require_iid(self.ctree, "Offer conditions")
        if not iid:
            return
        v = ui.ask_form(self.win, "Staff outcome", [
            ("outcome", "Outcome (blank = automatic)", "readonly",
             ("",) + er.MANUAL_OUTCOMES)])
        if v is not None:
            er.set_manual_outcome(int(iid), v["outcome"] or None,
                                  by=ui.current_username())
            self._changed()

    def _evaluate(self, result_type: str) -> None:
        ev = er.evaluate(self.aid, result_type=result_type)
        messagebox.showinfo(
            "Evaluation", f"{result_type} results ({ev.results_used}): "
            f"overall {ev.overall}", parent=self.win)
        self._changed()


def import_results_csv(parent: tk.Misc, result_type: str = "Actual") -> None:
    path = filedialog.askopenfilename(
        parent=parent, title="GCSE results CSV",
        filetypes=[("CSV", "*.csv"), ("All files", "*")])
    if not path:
        return
    try:
        n, errors = er.import_results_csv(path, result_type=result_type,
                                          entered_by=ui.current_username())
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Import results", str(e), parent=parent)
        return
    msg = f"{n} result(s) recorded."
    if errors:
        msg += f"\n\n{len(errors)} problem(s):\n" + "\n".join(errors[:30])
    messagebox.showinfo("Import results", msg, parent=parent)


def open_applicant_gcses(parent: tk.Misc, applicant_id: str,
                         on_change=None) -> ApplicantGcseDialog:
    return ApplicantGcseDialog(parent, applicant_id, on_change=on_change)


def open_entry_requirements_window(parent=None) -> None:
    win = ui.new_window(parent, "Entry requirements")
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    EntryRequirementsTab(nb)


# ── Offer dialog helpers (used by admissions_views.OfferDialog) ─────

def conditions_from_requirements(parent: tk.Misc,
                                 applicant_id: str) -> str | None:
    """Generate structured conditions from the entry requirements and
    return their wording (None when nothing applies or on error)."""
    try:
        rows = er.generate_conditions(applicant_id)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Conditions", str(e), parent=parent)
        return None
    if not rows:
        messagebox.showinfo("Conditions", "No entry requirements apply to "
                            "this applicant's choices yet (Entry "
                            "Requirements tab).", parent=parent)
        return None
    return er.conditions_text(applicant_id)


def save_structured_offer(parent: tk.Misc, applicant_id: str,
                          decided_by: str | None, expiry: str) -> bool:
    """Make a conditional offer whose text comes from the stored rows."""
    try:
        er.make_structured_offer(applicant_id, regenerate=False,
                                 decided_by=decided_by, expiry=expiry)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Offer", str(e), parent=parent)
        return False
    return True
