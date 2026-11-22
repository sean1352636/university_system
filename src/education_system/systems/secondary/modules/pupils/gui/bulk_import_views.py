"""Bulk Import screens: the five old Bulk Operations actions (import, export,
bulk update, bulk delete, format help) plus template download and an import
history with undo. Rules live in :mod:`modules.pupils.domain.bulk_import`; long runs happen
on a worker thread (no Tk calls there)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import tk_threads, window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.pupils.domain import bulk_import as B
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)

_ERRORS = (B.ValidationError, B.PermissionDenied, B.NotFound)
_STATUS_COLOURS = {B.READY: "#060", B.WARNING: "#a60", B.DUPLICATE: "#a60", B.ERROR: "#a00"}


_problems = W.problems


def _tree(parent: tk.Misc, columns, height: int = 12, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select, stretch={"name", "why", "desc"})


def _run_with_progress(win: tk.Misc, label: ttk.Label, bar: ttk.Progressbar,
                       work: Callable[[Callable[[int, int], None]], object],
                       done: Callable[[object, Exception | None], None]) -> None:
    """Run ``work(progress)`` on a thread; progress and the result come back to Tk."""
    def progress(i: int, n: int) -> None:
        def show() -> None:
            bar.configure(maximum=n, value=i)
            label.configure(text=f"{i} of {n}…")
        tk_threads.ui(win, show)

    def run() -> None:
        try:
            result = work(progress)
        except Exception as e:  # noqa: BLE001
            if not isinstance(e, _ERRORS):
                logger.exception("Bulk job failed")
            tk_threads.ui(win, done, None, e)
            return
        tk_threads.ui(win, done, result, None)

    tk_threads.start_thread(win, run, name="secondary-bulk")


# ── Page ─────────────────────────────────────────────────────────────

def draw_bulk_import(parent: ttk.Frame, *, principal: Principal,
                     open_pupil: Callable[[int], None]) -> None:
    activity_log.record("bulk.open")
    ttk.Label(parent, text="Bulk Import", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, text="Import, export, or batch-edit pupil records. Every import and "
                           "update can be undone from the history below.",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    top = ttk.Frame(parent)
    top.pack(fill="x")
    actions = ttk.Frame(top)
    actions.pack(side="left", anchor="n")
    hist_box = ttk.LabelFrame(parent, text="Import history", padding=8)
    hist_box.pack(fill="both", expand=True, pady=(10, 0))
    tree = _tree(hist_box, (("id", "#", 45), ("when", "When", 140), ("who", "By", 90),
                            ("kind", "Type", 65), ("desc", "What", 380), ("done", "Done", 55),
                            ("failed", "Failed", 55), ("status", "Status", 110)), height=10)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for j in B.list_jobs():
            tree.insert("", "end", iid=str(j.job_id), values=(
                j.job_id, j.created_at, j.created_by, j.kind, j.description, j.done, j.failed,
                j.status.replace("_", " ")))

    def selected_job() -> B.Job | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Import history", "Select a job first.", parent=parent)
            return None
        return B.get_job(int(sel[0]))

    def view(_e=None) -> None:
        job = selected_job()
        if job:
            job_dialog(parent, job, open_pupil)

    def undo() -> None:
        job = selected_job()
        if job is None:
            return
        if not job.can_undo:
            messagebox.showinfo("Undo", "This job can't be undone"
                                + (" - deletes are permanent." if job.kind == "delete"
                                   else "."), parent=parent)
            return
        what = ("remove the pupils it added (and their logins)" if job.kind == "import"
                else "put the old values back")
        if not messagebox.askyesno("Undo", f"Undo job #{job.job_id}?\n\n{job.description}\n\n"
                                   f"This will {what}. Pupils changed since are left alone.",
                                   parent=parent):
            return
        try:
            undone, kept = B.undo_job(job.job_id, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Undo", _problems(e), parent=parent)
            return
        msg = f"{undone} undone."
        if kept:
            msg += f"\n\n{len(kept)} left alone:\n" + "\n".join(
                f"• {a or '?'}: {why}" for a, why in kept[:15])
        messagebox.showinfo("Undo", msg, parent=parent)
        refresh()

    tree.bind("<Double-1>", view)
    hb = ttk.Frame(hist_box)
    hb.pack(fill="x", pady=(6, 0))
    ttk.Button(hb, text="View details…", command=view).pack(side="left")
    ttk.Button(hb, text="Undo…", command=undo).pack(side="left", padx=6)
    ttk.Button(hb, text="↻ Refresh", command=refresh).pack(side="right")

    def template() -> None:
        path = filedialog.asksaveasfilename(parent=parent, defaultextension=".csv",
                                            initialfile="pupil_import_template.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            B.write_template(path)
            activity_log.record("bulk.template")
            messagebox.showinfo("Template", f"Saved {path}", parent=parent)

    for label, cmd in (
            ("Import pupils from CSV…", lambda: import_flow(parent, principal, refresh)),
            ("Export pupils to CSV…", lambda: export_dialog(parent, principal)),
            ("Bulk update field…", lambda: update_dialog(parent, principal, refresh)),
            ("Bulk delete pupils…", lambda: delete_dialog(parent, principal, refresh)),
            ("CSV format help", lambda: messagebox.showinfo("CSV format", B.FORMAT_HELP,
                                                            parent=parent)),
            ("Download template…", template)):
        ttk.Button(actions, text=label, command=cmd, width=30).pack(anchor="w", pady=3)
    refresh()


def job_dialog(owner: tk.Misc, job: B.Job, open_pupil) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Job #{job.job_id}")
    window_sizing.fit(win, "820x520", (600, 360))
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=job.description, font=("", 11, "bold"), wraplength=760).pack(anchor="w")
    ttk.Label(frm, text=f"{job.created_at} by {job.created_by} · {job.status.replace('_', ' ')}"
                        + (f" ({job.undone_at} by {job.undone_by})" if job.undone_at else ""),
              foreground="#666").pack(anchor="w", pady=(0, 6))
    tree = _tree(frm, (("line", "Line", 50), ("adm", "Adm. no", 100), ("outcome", "Outcome", 80),
                       ("why", "Detail", 500)))
    for it in B.job_items(job.job_id):
        d = it["detail"]
        detail = it["message"] or (f"{d['field']}: {d['from']} → {d['to']}"
                                   if "field" in d else "")
        tree.insert("", "end", iid=str(it["item_id"]), values=(
            it["line"] or "", it["admission_no"] or "", it["outcome"], detail),
            tags=(str(it["pupil_id"] or ""),))

    def open_selected(_e=None) -> None:
        sel = tree.selection()
        if sel:
            pid = tree.item(sel[0], "tags")
            if pid and pid[0] and P.get_pupil(int(pid[0])):
                win.destroy()
                open_pupil(int(pid[0]))

    tree.bind("<Double-1>", open_selected)
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))


# ── Import ───────────────────────────────────────────────────────────

def import_flow(owner: tk.Misc, principal: Principal, after: Callable[[], None]) -> None:
    path = filedialog.askopenfilename(parent=owner, title="Choose a pupil file",
                                      filetypes=[("CSV or Excel", "*.csv *.xlsx"),
                                                 ("All files", "*.*")])
    if not path:
        return
    try:
        pv = B.preview(B.read_file(path))
    except _ERRORS as e:
        messagebox.showerror("Import", _problems(e), parent=owner)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Reading import file failed")
        messagebox.showerror("Import", f"The file couldn't be read:\n{e}", parent=owner)
        return
    activity_log.record("bulk.preview", rows=len(pv.rows), ready=pv.count(B.READY, B.WARNING),
                        duplicates=pv.count(B.DUPLICATE), errors=pv.count(B.ERROR))
    preview_window(owner, pv, principal, after)


def preview_window(owner: tk.Misc, pv: B.Preview, principal: Principal,
                   after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Import preview - {pv.file_name}")
    window_sizing.fit(win, "1100x720", (800, 500))
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    foot = ttk.Frame(frm)
    foot.pack(side="bottom", fill="x", pady=(8, 0))
    ttk.Label(frm, text=f"{len(pv.rows)} rows: {pv.count(B.READY)} ready, "
                        f"{pv.count(B.WARNING)} ready but worth checking, "
                        f"{pv.count(B.DUPLICATE)} possible duplicates, "
                        f"{pv.count(B.ERROR)} with errors (skipped). Nothing is saved yet.",
              font=("", 10, "bold"), wraplength=1000).pack(anchor="w")
    if pv.ignored_columns:
        ttk.Label(frm, text="Columns ignored: " + ", ".join(pv.ignored_columns),
                  foreground="#a60").pack(anchor="w")
    show_var = tk.StringVar(value="All")
    sf = ttk.Frame(frm)
    sf.pack(fill="x", pady=4)
    ttk.Label(sf, text="Show").pack(side="left")
    ttk.Combobox(sf, textvariable=show_var, state="readonly", width=20,
                 values=["All", *B.STATUS_LABELS.values()]).pack(side="left", padx=4)
    tree = _tree(frm, (("line", "Line", 45), ("name", "Name", 180), ("dob", "Born", 85),
                       ("yr", "Yr", 30), ("form", "Form", 50), ("contacts", "Contacts", 65),
                       ("status", "Status", 120), ("why", "Problems / notes", 480)), height=18)
    for status, colour in _STATUS_COLOURS.items():
        tree.tag_configure(status, foreground=colour)

    def fill(*_a) -> None:
        tree.delete(*tree.get_children())
        for r in pv.rows:
            label = B.STATUS_LABELS[r.status]
            if show_var.get() not in ("All", label):
                continue
            notes = r.problems + r.warnings
            if r.existing:
                notes.insert(0, f"Same name and date of birth as {r.existing}")
            tree.insert("", "end", values=(r.line, r.name, r.pupil.get("date_of_birth", ""),
                                           r.pupil.get("year_group", ""),
                                           r.pupil.get("form_group", ""), len(r.contacts), label,
                                           "; ".join(notes)), tags=(r.status,))

    show_var.trace_add("write", fill)
    fill()

    dup_var = tk.BooleanVar(value=False)
    login_var = tk.BooleanVar(value=True)
    opts = ttk.Frame(foot)
    opts.pack(fill="x")
    if pv.count(B.DUPLICATE):
        ttk.Checkbutton(opts, variable=dup_var, text=f"Also add the {pv.count(B.DUPLICATE)} "
                        "possible duplicates (only if they really are different pupils)").pack(
            anchor="w")
    ttk.Checkbutton(opts, variable=login_var, text="Create logins and school e-mail addresses "
                    "and send welcome e-mails (as Add Pupil does)").pack(anchor="w")
    status = ttk.Label(foot, foreground="#555")
    status.pack(anchor="w", pady=(4, 0))
    bar = ttk.Progressbar(foot, mode="determinate")
    btns = ttk.Frame(foot)
    btns.pack(anchor="e", pady=(4, 0))
    go_btn = ttk.Button(btns, text="Import")
    cancel_btn = ttk.Button(btns, text="Cancel", command=win.destroy)
    cancel_btn.pack(side="right")
    go_btn.pack(side="right", padx=(0, 6))

    def go() -> None:
        n = pv.count(B.READY, B.WARNING) + (pv.count(B.DUPLICATE) if dup_var.get() else 0)
        if not n:
            messagebox.showinfo("Import", "Nothing to import.", parent=win)
            return
        if not messagebox.askyesno("Import", f"Add {n} pupil{'s' if n != 1 else ''}?",
                                   parent=win):
            return
        go_btn.configure(state="disabled")
        cancel_btn.configure(state="disabled")
        win.protocol("WM_DELETE_WINDOW", lambda: None)  # don't close mid-run
        bar.pack(fill="x", pady=(4, 0))
        logins, dups = login_var.get(), dup_var.get()

        def work(progress):
            result = B.run_import(pv, actor=principal, include_duplicates=dups,
                                  create_logins=logins, progress=progress)
            report = None
            if result.welcome_message_ids:
                tk_threads.ui(win, lambda: status.configure(text="Sending welcome e-mails…"))
                try:
                    for mid in result.welcome_message_ids:
                        report = E.deliver(mid, principal=principal)
                except Exception as e:  # noqa: BLE001 - saved; retry from Email
                    logger.exception("Welcome delivery failed")
                    report = e
            return result, report

        def done(out, err) -> None:
            win.destroy()
            if err is not None:
                messagebox.showerror("Import", _problems(err), parent=owner)
                after()
                return
            result, report = out
            lines = [f"{len(result.created)} pupil{'s' if len(result.created) != 1 else ''} "
                     f"added (job #{result.job_id})."]
            if result.failed:
                lines.append(f"\n{len(result.failed)} not added / partly added:")
                lines += [f"• line {ln}: {why}" for ln, why in result.failed[:15]]
            if result.welcome_message_ids:
                lines.append(f"\n{len(result.welcome_message_ids)} welcome e-mail(s) "
                             + (f"saved, but delivery failed: {report} - retry from Email."
                                if isinstance(report, Exception) else
                                f"handled ({E.delivery_mode()} mode)."))
            if result.login_errors:
                lines.append(f"\n{len(result.login_errors)} login problem(s) - use Create "
                             "login on the pupil's profile:")
                lines += [f"• {a}: {why}" for a, why in result.login_errors[:10]]
            messagebox.showinfo("Import finished", "\n".join(lines), parent=owner)
            after()

        _run_with_progress(win, status, bar, work, done)

    go_btn.configure(command=go)


# ── Export ───────────────────────────────────────────────────────────

def export_dialog(owner: tk.Misc, principal: Principal) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Export pupils")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    statuses = {"On roll": "on_roll", "Left": "left", "All": None}
    status = ttk.Combobox(frm, values=list(statuses), state="readonly", width=10)
    status.set("On roll")
    year = ttk.Combobox(frm, values=["All", *map(str, P.YEAR_GROUPS)], state="readonly", width=6)
    year.set("All")
    form = ttk.Combobox(frm, values=["All", *P.form_groups_in_use()], state="readonly", width=8)
    form.set("All")
    for r, (label, w) in enumerate((("Pupils", status), ("Year group", year), ("Form", form))):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        w.grid(row=r, column=1, sticky="w", pady=2)
    sens = tk.BooleanVar(value=False)
    cont = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, variable=cont, text="Parent contacts").grid(row=3, column=0,
                                                                     columnspan=2, sticky="w")
    ttk.Checkbutton(frm, variable=sens, text="SEN, FSM, EAL and notes (sensitive)").grid(
        row=4, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="Keep exported files safe and delete them when done.",
              foreground="#888").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def go() -> None:
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv",
                                            initialfile="pupils.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = B.export_csv(path, actor=principal, roll_status=statuses[status.get()],
                             year_group=None if year.get() == "All" else int(year.get()),
                             form_group=None if form.get() == "All" else form.get(),
                             include_sensitive=sens.get(), include_contacts=cont.get())
        except _ERRORS as e:
            messagebox.showerror("Export", _problems(e), parent=win)
            return
        except OSError as e:
            messagebox.showerror("Export", f"Couldn't write the file:\n{e}", parent=win)
            return
        win.destroy()
        messagebox.showinfo("Export", f"{n} pupil{'s' if n != 1 else ''} written to\n{path}",
                            parent=owner)

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Export…", command=go).pack(side="right", padx=(0, 6))


# ── Choosing pupils (update + delete) ──────────────────────────────────

class _PupilChooser:
    """Pupils by year group, form group, or a pasted list of admission numbers / UPNs."""

    def __init__(self, parent: ttk.Frame, *, allow_groups: bool = True):
        self.mode = tk.StringVar(value="year" if allow_groups else "refs")
        box = ttk.LabelFrame(parent, text="Which pupils", padding=6)
        box.pack(fill="x", pady=(6, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.year = ttk.Combobox(row, values=list(map(str, P.YEAR_GROUPS)), state="readonly",
                                 width=5)
        self.form = ttk.Combobox(row, values=P.form_groups_in_use(), state="readonly", width=8)
        if allow_groups:
            ttk.Radiobutton(row, text="Year group", value="year", variable=self.mode).pack(
                side="left")
            self.year.pack(side="left", padx=(2, 12))
            ttk.Radiobutton(row, text="Form", value="form", variable=self.mode).pack(side="left")
            self.form.pack(side="left", padx=(2, 12))
            ttk.Radiobutton(row, text="These admission numbers / UPNs:", value="refs",
                            variable=self.mode).pack(side="left")
        else:
            ttk.Label(row, text="Admission numbers or UPNs (one per line or comma-separated):"
                      ).pack(side="left")
        self.refs = tk.Text(box, width=70, height=4)
        self.refs.pack(fill="x", pady=(4, 0))

    def pupils(self) -> tuple[list[P.Pupil], list[str]]:
        mode = self.mode.get()
        if mode == "year":
            return (P.list_pupils(year_group=int(self.year.get())) if self.year.get() else []), []
        if mode == "form":
            return (P.list_pupils(form_group=self.form.get()) if self.form.get() else []), []
        return B.resolve_refs(self.refs.get("1.0", "end"))


# ── Bulk update ──────────────────────────────────────────────────────

_VALUE_CHOICES = {
    "year_group": [str(y) for y in P.YEAR_GROUPS],
    "sen_status": list(P.SEN_STATUSES),
    "fsm_eligible": ["yes", "no"],
    "eal": ["yes", "no"],
}


def _set_up_forms() -> list[str]:
    from education_system.systems.secondary.modules.curriculum.domain import form_groups
    return sorted({f.name for f in form_groups.list_forms()})


def update_dialog(owner: tk.Misc, principal: Principal, after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Bulk update field")
    window_sizing.fit(win, "860x640", (700, 480))
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    foot = ttk.Frame(frm)
    foot.pack(side="bottom", fill="x", pady=(8, 0))
    top = ttk.Frame(frm)
    top.pack(fill="x")
    labels = {v: k for k, v in B.UPDATE_FIELDS.items()}
    ttk.Label(top, text="Field:").grid(row=0, column=0, sticky="w", pady=4)
    field_cb = ttk.Combobox(top, values=list(labels), state="readonly", width=34)
    field_cb.grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(top, text="New value:").grid(row=1, column=0, sticky="w", pady=4)
    value_cb = ttk.Combobox(top, width=12)
    value_cb.grid(row=1, column=1, sticky="w", padx=4)
    hint = ttk.Label(top, foreground="#888")
    hint.grid(row=1, column=2, sticky="w")

    def on_field(_e=None) -> None:
        key = labels.get(field_cb.get())
        choices = _VALUE_CHOICES.get(key or "")
        value_cb.set("")
        value_cb.configure(values=choices or _set_up_forms(),
                           state="readonly" if choices else "normal")
        hint.configure(text="SEN: N none, K support, E EHC plan" if key == "sen_status" else
                       "Forms set up in Form Groups; blank clears" if key == "form_group"
                       else "")

    field_cb.bind("<<ComboboxSelected>>", on_field)
    chooser = _PupilChooser(frm)
    ttk.Label(frm, text="No 'record updated' e-mails are sent for bulk changes. To take pupils "
                        "off roll use Enrolment & Leavers.", foreground="#888").pack(
        anchor="w", pady=(4, 0))
    tree = _tree(frm, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("before", "Now", 90),
                       ("after", "Will be", 90), ("why", "Note", 300)))
    tree.tag_configure("skip", foreground="#888")
    tree.tag_configure("bad", foreground="#a00")
    status = ttk.Label(foot, foreground="#555")
    status.pack(anchor="w")
    bar = ttk.Progressbar(foot, mode="determinate")
    state: dict = {"ids": []}

    def preview() -> bool:
        tree.delete(*tree.get_children())
        key = labels.get(field_cb.get())
        if not key:
            status.configure(text="Choose a field.")
            return False
        pupils, missing = chooser.pupils()
        try:
            checks = B.preview_update(key, value_cb.get(), pupils)
        except _ERRORS as e:
            status.configure(text=_problems(e))
            return False
        for ref in missing:
            tree.insert("", "end", values=(ref, "", "", "", "Not found"), tags=("bad",))
        for c in checks:
            note = c.problem or ("" if c.changes else "Already set")
            tree.insert("", "end", values=(c.pupil.admission_no, c.pupil.display_name,
                                           B._show(c.before), B._show(c.after) if
                                           c.after is not None else "", note),
                        tags=("bad",) if c.problem else () if c.changes else ("skip",))
        state["ids"] = [c.pupil.pupil_id for c in checks if c.changes]
        state["key"], state["value"] = key, value_cb.get()
        status.configure(text=f"{len(state['ids'])} will change, "
                              f"{len(checks) - len(state['ids'])} unchanged or refused, "
                              f"{len(missing)} not found.")
        return True

    def apply() -> None:
        if not preview() or not state["ids"]:
            return
        n = len(state["ids"])
        if not messagebox.askyesno("Bulk update", f"Set {field_cb.get()} for {n} pupil"
                                   f"{'s' if n != 1 else ''}?", parent=win):
            return
        bar.pack(fill="x", pady=(4, 0))
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        def done(out, err) -> None:
            win.destroy()
            if err is not None:
                messagebox.showerror("Bulk update", _problems(err), parent=owner)
            else:
                job_id, failed = out
                messagebox.showinfo("Bulk update", f"Done (job #{job_id})."
                                    + (f"\n\n{len(failed)} not changed:\n" + "\n".join(
                                        f"• {a}: {w}" for a, w in failed[:15]) if failed
                                       else ""), parent=owner)
            after()

        _run_with_progress(win, status, bar, lambda progress: B.run_update(
            state["key"], state["value"], state["ids"], actor=principal, progress=progress),
            done)

    btns = ttk.Frame(foot)
    btns.pack(anchor="e", pady=(4, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(btns, text="Apply", command=apply).pack(side="right", padx=(0, 6))
    ttk.Button(btns, text="Preview", command=preview).pack(side="right", padx=(0, 6))


# ── Bulk delete ──────────────────────────────────────────────────────

def delete_dialog(owner: tk.Misc, principal: Principal, after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Bulk delete pupils")
    window_sizing.fit(win, "800x620", (660, 480))
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    foot = ttk.Frame(frm)
    foot.pack(side="bottom", fill="x", pady=(8, 0))
    ttk.Label(frm, text="Only for records created in error (for example a wrong import - "
                        "Undo in Import history is usually better). Pupils who have left "
                        "should be recorded in Enrolment & Leavers instead. Each deleted record "
                        "is kept in the audit trail and loses its login.",
              foreground="#a00", wraplength=740, justify="left").pack(anchor="w")
    chooser = _PupilChooser(frm, allow_groups=False)
    tree = _tree(frm, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("yr", "Yr", 35),
                       ("status", "Status", 80), ("why", "Note", 260)), height=8)
    ttk.Label(foot, text="Reason *").grid(row=0, column=0, sticky="w")
    reason = ttk.Entry(foot, width=50)
    reason.grid(row=0, column=1, sticky="w", padx=4)
    ttk.Label(foot, text="Type DELETE to confirm").grid(row=1, column=0, sticky="w", pady=4)
    confirm = ttk.Entry(foot, width=12)
    confirm.grid(row=1, column=1, sticky="w", padx=4)
    status = ttk.Label(foot, foreground="#555")
    status.grid(row=2, column=0, columnspan=2, sticky="w")
    bar = ttk.Progressbar(foot, mode="determinate")
    found: list[P.Pupil] = []

    def find() -> None:
        tree.delete(*tree.get_children())
        pupils, missing = chooser.pupils()
        found[:] = pupils
        for ref in missing:
            tree.insert("", "end", values=(ref, "", "", "", "Not found"))
        for p in pupils:
            tree.insert("", "end", values=(p.admission_no, p.display_name, p.year_group,
                                           p.roll_status_label, ""))
        status.configure(text=f"{len(pupils)} found, {len(missing)} not found.")

    def go() -> None:
        find()
        if not found:
            return
        if confirm.get().strip() != "DELETE":
            status.configure(text="Type DELETE to confirm.")
            return
        if not reason.get().strip():
            status.configure(text="Give a reason.")
            return
        bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        ids = [p.pupil_id for p in found]

        def done(out, err) -> None:
            win.destroy()
            if err is not None:
                messagebox.showerror("Bulk delete", _problems(err), parent=owner)
            else:
                job_id, failed = out
                messagebox.showinfo("Bulk delete", f"{len(ids) - len(failed)} deleted "
                                    f"(job #{job_id})." + (f"\n\n{len(failed)} failed:\n"
                                                           + "\n".join(f"• {a}: {w}" for a, w
                                                                       in failed[:15])
                                                           if failed else ""), parent=owner)
            after()

        _run_with_progress(win, status, bar, lambda progress: B.run_delete(
            ids, actor=principal, reason=reason.get(), progress=progress), done)

    btns = ttk.Frame(foot)
    btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(6, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(btns, text="Delete", command=go).pack(side="right", padx=(0, 6))
    ttk.Button(btns, text="Find", command=find).pack(side="right", padx=(0, 6))
