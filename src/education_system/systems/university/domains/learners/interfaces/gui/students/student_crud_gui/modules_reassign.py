# Auto-generated module (split from student_crud_gui.py)
"""Reassign a student's optional modules.

The options offered are the student's own course structure for their year
(``registration.structure``: optional designations for the course, with
the compulsory modules shown for context). Staff tick the options the
student should take; the changes go through module registration's
``enrol`` / ``drop`` (prerequisites, exclusions, capacity and waitlist,
credit limits, the ``module_enrolments`` mirror and the status log), then
its post-commit side effects.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_connection

from .authorization import require_student_permission

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

from .sync.chat_rooms import _sync_module_chat_rooms

from .sync.atas import _resync_atas_after_module_change


def _actor(owner) -> str:
    user = getattr(getattr(owner, "auth", None), "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "university CRUD GUI")


# modules.module_type pools behind the old "reassign" button, used only when
# the course has no optional modules designated for the student's year.
OPTION_POOLS = {"optional": ("optional",), "CS": ("CS_optional",), "DS": ("DS_optional",)}
POOL_OVERRIDE = "optional module pool (no optional designations for this course and year)"


def _option_pool(conn, student_id, course, module_type):
    """``(note, options)`` from the catalogue's optional-module pool.

    The general pool, plus the course's own pool when one exists (``CS`` ->
    ``CS_optional``). Each option carries the student's current status.
    """
    types = list(OPTION_POOLS.get(module_type, (module_type,)))
    if module_type == "optional" and course and f"{course}_optional" not in types:
        types.append(f"{course}_optional")
    marks = ", ".join("?" for _ in types)
    rows = conn.execute(
        "SELECT module_code, module_name, NULLIF(credits, 0) FROM modules "
        f"WHERE module_type IN ({marks}) ORDER BY module_type, module_code", types).fetchall()
    states = {r[0]: r[1] for r in conn.execute(
        "SELECT module_code, status FROM student_modules WHERE student_id = ?", (str(student_id),))}
    options = [{"code": r[0], "name": r[1] or r[0], "credits": r[2],
                "state": "Enrolled" if str(states.get(r[0], "")).lower() == "enrolled" else states.get(r[0], "")}
               for r in rows]
    if not options:
        return None, []
    note = (f"No optional modules are designated for {course} in Module Management, so the "
            f"catalogue's {' / '.join(types)} modules are offered; enrolling one is logged as a staff override.")
    return note, options


def reassign_modules(self, student_id, module_type, cursor=None, parent=None):
    """Let staff choose a student's optional modules from their course structure.

    *module_type* is kept for existing callers; the options always come from
    the student's course and year. *cursor* is accepted for compatibility and
    ignored: registration commits its own transaction.
    """
    parent = parent or getattr(self, "root", None)
    if not require_student_permission(self, "update_any_student", "reassign the modules of"):
        return

    from education_system.systems.university.application.modules import registration

    pool_note = None
    try:
        conn = get_connection()
        try:
            registration.ensure(conn)
            view = registration.overview(conn, student_id)
            if not view["blocked"] and not view["structure"]["optional"]:
                pool_note, view["structure"]["optional"] = _option_pool(
                    conn, student_id, view["student"]["course"], module_type)
        finally:
            conn.close()
    except Exception as e:
        logger.exception("reassign_modules: could not load structure for %s", student_id)
        messagebox.showerror(_t("common.error"), _t("student.failed_reassign_modules", error=str(e)), parent=parent)
        return

    s, plan, rules = view["student"], view["structure"], view["rules"]
    if view["blocked"]:
        messagebox.showwarning(_t("common.warning"), view["blocked"], parent=parent)
        return
    options = plan["optional"]

    win = tk.Toplevel(parent)
    win.title(f"Optional modules - {s['name']} ({s['student_id']})")
    win.geometry("760x560")
    if parent is not None:
        win.transient(parent)

    head = (f"Course {s['course']}, year {s['year_of_study']} (from {plan['source'] or 'no structure'}). "
            f"Enrolled credits: {view['credits']}"
            + (f" (+{view['unknown_credits']} module(s) with no credits recorded)" if view["unknown_credits"] else "")
            + f"; target {rules['target_credits']}, maximum {rules['max_credits']}.")
    limits = f"Options: at least {rules['min_optional'] or 0}" + (
        f", at most {rules['max_optional']}" if rules.get("max_optional") is not None else "")
    ttk.Label(win, text=head, wraplength=720).pack(anchor=tk.W, padx=10, pady=(10, 2))
    ttk.Label(win, text=limits, foreground="gray").pack(anchor=tk.W, padx=10)
    if pool_note:
        ttk.Label(win, text=pool_note, foreground="gray", wraplength=720).pack(anchor=tk.W, padx=10)

    compulsory = ", ".join(m["code"] for m in plan["compulsory"]) or "none recorded"
    ttk.Label(win, text=f"Compulsory (enrolled by registration, not changed here): {compulsory}",
              wraplength=720).pack(anchor=tk.W, padx=10, pady=(4, 6))

    # Bottom bar first so it stays visible when the window is short.
    bar = ttk.Frame(win)
    bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
    reason_frame = ttk.Frame(win)
    reason_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
    ttk.Label(reason_frame, text="Reason / override (needed only to go past a rule):").pack(side=tk.LEFT)
    reason_var = tk.StringVar()
    ttk.Entry(reason_frame, textvariable=reason_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

    columns = ("code", "name", "credits", "state")
    tree = ttk.Treeview(win, columns=columns, show="headings", selectmode="extended")
    for col, label, width in (("code", "Module", 110), ("name", "Name", 330),
                              ("credits", "Credits", 70), ("state", "Current", 140)):
        tree.heading(col, text=label)
        tree.column(col, width=width)
    tree.pack(fill=tk.BOTH, expand=True, padx=10)

    if not options:
        tree.insert("", "end", values=("", f"No optional modules are designated for {s['course']} "
                                           f"year {s['year_of_study']}", "", ""))
    current = set()
    for m in options:
        iid = tree.insert("", "end", iid=m["code"], values=(
            m["code"], m["name"], m["credits"] if m["credits"] is not None else "-", m["state"] or ""))
        if m["state"] == "Enrolled":
            current.add(m["code"])
            tree.selection_add(iid)

    ttk.Label(win, text="Select (Ctrl/Shift-click) every option the student should take.",
              foreground="gray").pack(anchor=tk.W, padx=10, pady=(4, 0))

    def apply():
        if not require_student_permission(self, "update_any_student", "reassign the modules of"):
            return
        chosen = {i for i in tree.selection() if i in {m["code"] for m in options}}
        to_add, to_drop = sorted(chosen - current), sorted(current - chosen)
        if not to_add and not to_drop:
            messagebox.showinfo(_t("common.info", default="Info"), "No changes to apply.", parent=win)
            return
        count_problems = []
        if len(chosen) < (rules["min_optional"] or 0):
            count_problems.append(f"{len(chosen)} option(s) chosen, the course needs at least {rules['min_optional']}")
        if rules.get("max_optional") is not None and len(chosen) > rules["max_optional"]:
            count_problems.append(f"{len(chosen)} option(s) chosen, the course allows {rules['max_optional']}")
        reason = reason_var.get().strip()
        if count_problems and not reason:
            messagebox.showwarning(_t("common.warning"), "; ".join(count_problems)
                                   + ".\n\nEnter a reason to override.", parent=win)
            return
        summary = "\n".join([f"Add: {', '.join(to_add)}" if to_add else "",
                             f"Drop: {', '.join(to_drop)}" if to_drop else ""]).strip()
        if not messagebox.askyesno(_t("common.confirm", default="Confirm"),
                                   f"Apply these module changes for {s['name']}?\n\n{summary}", parent=win):
            return

        actor = _actor(self)
        results, added, removed = {}, [], []
        conn = get_connection()
        try:
            registration.ensure(conn)
            # One savepoint per module: a refused module never undoes the others.
            for code in to_drop:
                conn.execute("SAVEPOINT reassign")
                try:
                    results[code] = "dropped: " + registration.drop(
                        conn, student_id, code, actor, staff=True, reason=reason or "reassigned by staff")
                    conn.execute("RELEASE reassign")
                    removed.append(code)
                except Exception as exc:
                    conn.execute("ROLLBACK TO reassign")
                    conn.execute("RELEASE reassign")
                    results[code] = f"not dropped: {exc}"
            for code in to_add:
                conn.execute("SAVEPOINT reassign")
                try:
                    # A pool option sits outside the course structure, so it
                    # is a recorded staff override, as registration requires.
                    outcome = registration.enrol(conn, student_id, code, actor, staff=True,
                                                 override=reason or (POOL_OVERRIDE if pool_note else None))
                    conn.execute("RELEASE reassign")
                    results[code] = str(outcome["result"])
                    if outcome["result"] != "waitlisted":
                        added.append(code)
                except Exception as exc:
                    conn.execute("ROLLBACK TO reassign")
                    conn.execute("RELEASE reassign")
                    results[code] = f"not enrolled: {exc}"
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.exception("reassign_modules failed for %s", student_id)
            messagebox.showerror(_t("common.error"), _t("student.failed_reassign_modules", error=str(e)), parent=win)
            return
        finally:
            conn.close()

        # After commit: fees, timetable, library holds, ATAS flags and the
        # confirmation e-mail for new enrolments, as module registration does.
        failed = []
        for code in added:
            failed += [f"{code}: {step}" for step in registration.side_effects(student_id, code)]
        try:
            _sync_module_chat_rooms(student_id, removed, added)
        except Exception as e:
            logger.warning(f"reassign_modules: chat-room sync failed for {student_id}: {e}")
        # Close ATAS rows for restricted modules just dropped (new ones were
        # flagged by side_effects). No-op without a visa record.
        try:
            if removed:
                _resync_atas_after_module_change(student_id, removed, [])
        except Exception as e:
            logger.warning(f"reassign_modules: ATAS resync failed for {student_id}: {e}")

        lines = [f"{code}: {result}" for code, result in results.items()]
        if failed:
            lines.append("\nFollow-up steps that failed: " + ", ".join(failed))
        ok = all(not r.startswith("not ") for r in results.values())
        show = messagebox.showinfo if ok else messagebox.showwarning
        show(_t("common.success") if ok else _t("common.warning"),
             _t("student.reassign_modules_success", module_type=module_type) + "\n\n" + "\n".join(lines),
             parent=win)
        win.destroy()

    ttk.Button(bar, text="Apply", command=apply, state=tk.NORMAL if options else tk.DISABLED).pack(side=tk.RIGHT, padx=5)
    ttk.Button(bar, text=_t("common.close", default="Close"), command=win.destroy).pack(side=tk.RIGHT)
