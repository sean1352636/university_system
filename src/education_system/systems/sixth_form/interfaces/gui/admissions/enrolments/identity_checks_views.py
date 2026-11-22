"""Photo / ID-document check window for enrolment."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_details,
)

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments.enrolment_common import (  # noqa: E501
    describe_error,
)

logger = logging.getLogger(__name__)


def _can_see() -> bool:
    try:
        return idc.can_see_immigration()
    except Exception:  # noqa: BLE001 — fail closed
        logger.exception("can_see_immigration failed")
        return False


def _visa_days() -> int:
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            course_changes,
        )
        return course_changes.get_setting(course_changes.VISA_WARNING_DAYS)
    except Exception:  # noqa: BLE001 — the module default
        logger.exception("Visa warning setting not read")
        return idc.VISA_WARNING_DAYS


#: Largest preview, in pixels; bigger photos are scaled down to fit.
PREVIEW_MAX = (480, 600)


def _load_preview(path: str, max_size: tuple[int, int] = PREVIEW_MAX):
    """A Tk image for a stored photo. JPEG (which ``tk.PhotoImage`` can't
    read) and PNG go through Pillow when it is installed, scaled to fit
    :data:`PREVIEW_MAX`; without Pillow only the formats Tk reads itself
    (PNG, GIF) preview."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return tk.PhotoImage(file=path)
    with Image.open(path) as im:
        im.load()
        shown = im.convert("RGBA") if im.mode not in ("RGB", "RGBA") else im.copy()
    shown.thumbnail(max_size)
    return ImageTk.PhotoImage(shown)


class IdentityChecksPanel:
    COLS = [("sid", "Student", 90), ("name", "Name", 200),
            ("photo", "Photo", 70), ("doc", "ID document", 200),
            ("last4", "No. (last 4)", 90), ("by", "Checked by", 120),
            ("on", "Checked on", 100), ("rts", "Right to study", 200),
            ("visa", "Visa", 120), ("expiry", "Visa expiry", 95),
            ("todo", "Outstanding", 260)]
    #: Columns only users who may see immigration data are shown.
    IMMIGRATION_COLS = ("rts", "visa", "expiry")
    VISA_COLS = [("sid", "Student", 90), ("name", "Name", 200),
                 ("visa", "Visa", 140), ("expiry", "Expiry", 95),
                 ("days", "Days left", 80), ("state", "State", 90)]
    HIST_COLS = [("on", "Checked on", 95), ("doc", "Document", 180),
                 ("last4", "Last 4", 60), ("rts", "Right to study", 200),
                 ("visa", "Visa", 110), ("expiry", "Visa expiry", 90),
                 ("by", "Checked by", 110), ("source", "Source", 180),
                 ("rec", "Recorded at", 140)]

    def __init__(self, parent: tk.Misc, student_id: str | None = None) -> None:
        self.parent = parent
        self.see = _can_see()
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Set photo…", command=self._photo).pack(
            side="left")
        ttk.Button(bar, text="Remove photo", command=self._rm_photo).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Open photo", command=self._open_photo).pack(
            side="left")
        ttk.Button(bar, text="Record ID check…", command=self._id).pack(
            side="left", padx=(12, 4))
        ttk.Button(bar, text="ID history…", command=self._history,
                   state="normal" if self.see else "disabled").pack(side="left")
        ttk.Button(bar, text="Visa expiring…", command=self._visas,
                   state="normal" if self.see else "disabled").pack(
            side="left", padx=4)
        ttk.Label(bar, text="Academic year:").pack(side="left", padx=(12, 2))
        self.year = ttk.Entry(bar, width=9)
        self.year.pack(side="left")
        self.missing = tk.BooleanVar(value=student_id is None)
        ttk.Checkbutton(bar, text="Outstanding only", variable=self.missing,
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search = ttk.Entry(bar, width=16)
        self.search.insert(0, student_id or "")
        self.search.pack(side="left", padx=2)
        ttk.Button(bar, text="Apply", command=self.refresh).pack(side="left")
        ttk.Label(parent, foreground="#555", text=(
            "Only the last four characters of a document number are kept. "
            "Recording an ID check ticks the onboarding ID item. A visa "
            "right to study needs the visa expiry date."
            + ("" if self.see else " Right to study and visa details are "
               "restricted to admissions, student records and safeguarding "
               "staff."))).pack(fill="x", padx=8)
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, self.COLS, height=20)
        if not self.see:
            self.tree["displaycolumns"] = [c for c, _h, _w in self.COLS
                                           if c not in self.IMMIGRATION_COLS]
        self.tree.bind("<Double-1>", lambda _e: self._history()
                       if self.see else None)
        self.refresh()

    def refresh(self) -> None:
        ui.clear(self.tree)
        try:
            students = {s.student_id: s for s in student_data.list_students()}
            checks = {c.student_id: c for c in idc.list_checks()}
            todo = {o.student_id: o for o in idc.outstanding_detail(
                self.year.get().strip() or None)}
            ids = sorted(todo) if self.missing.get() else sorted(students)
        except Exception as e:  # noqa: BLE001
            logger.exception("Identity checks failed to load")
            messagebox.showerror("Identity checks", describe_error(e),
                                 parent=self.parent)
            return
        q = self.search.get().strip().lower()
        for sid in ids:
            s = students.get(sid)
            name = s.full_name if s else ""
            if q and q not in sid.lower() and q not in name.lower():
                continue
            c = checks.get(sid)
            self.tree.insert("", "end", iid=sid, values=(
                sid, name, "Yes" if c and c.has_photo else "—",
                (c.id_document_type or "—") if c else "—",
                (c.id_number_last4 or "") if c else "",
                (c.id_checked_by or "") if c else "",
                (c.id_checked_on or "") if c else "",
                (c.right_to_study or "") if c else "",
                (c.visa_type or "") if c else "",
                (c.visa_expiry or "") if c else "",
                ", ".join(todo[sid].problems) if sid in todo else ""))

    def _sid(self) -> str | None:
        return ui.require_iid(self.tree, "Identity checks")

    def _photo(self) -> None:
        sid = self._sid()
        if not sid:
            return
        path = filedialog.askopenfilename(
            parent=self.parent, title="Student photo",
            filetypes=[("Images", " ".join(f"*{e}" for e in
                                           idc.PHOTO_EXTENSIONS))])
        if not path:
            return
        try:
            idc.set_photo(sid, path, by=ui.current_username())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Photo", str(e), parent=self.parent)
        self.refresh()

    def _rm_photo(self) -> None:
        sid = self._sid()
        if sid and messagebox.askyesno("Photo", "Remove this student's photo?",
                                       parent=self.parent):
            try:
                removed = idc.remove_photo(sid)
            except Exception as e:  # noqa: BLE001 — AccessDenied / file / DB
                logger.warning("remove_photo(%s) failed: %s", sid, e)
                messagebox.showerror("Photo", str(e), parent=self.parent)
                return
            if not removed:
                messagebox.showinfo("Photo", "There was no photo to remove.",
                                    parent=self.parent)
            self.refresh()

    def _open_photo(self) -> None:
        sid = self._sid()
        c = idc.get_check(sid) if sid else None
        if not (c and c.has_photo):
            messagebox.showinfo("Photo", "No photo on file.",
                                parent=self.parent)
            return
        win = make_toplevel(self.parent)
        win.title(f"Photo — {sid}")
        try:
            img = _load_preview(c.photo_path)
            lbl = ttk.Label(win, image=img)
            lbl.image = img  # type: ignore[attr-defined]  # keep a reference
            lbl.pack(padx=8, pady=8)
        except (tk.TclError, OSError, ValueError) as exc:
            logger.warning("Photo preview failed for %s: %s", sid, exc)
            ttk.Label(win, text=f"Stored at:\n{c.photo_path}\n\n(This image "
                      f"cannot be previewed here: {exc})").pack(padx=12,
                                                                pady=12)

    def _visas(self) -> None:
        """Learners whose visa has expired or expires soon (the window is
        the Visa warning setting)."""
        try:
            days = _visa_days()
            rows = idc.visa_expiring(days)
        except Exception as e:  # noqa: BLE001 — AccessDenied shown plainly
            messagebox.showerror("Visa expiring", describe_error(e),
                                 parent=self.parent)
            return
        names = {s.student_id: s.full_name for s in student_data.list_students()}
        win = make_toplevel(self.parent)
        win.title(f"Visas expired or expiring within {days} days")
        win.geometry("820x420")
        ttk.Button(win, text="Close", command=win.destroy).pack(
            side="bottom", anchor="e", padx=8, pady=8)
        ttk.Label(win, foreground="#555", text=(
            f"{len(rows)} learner(s) with a live enrolment, soonest first.")
                  ).pack(anchor="w", padx=8, pady=(8, 2))
        holder = ttk.Frame(win)
        holder.pack(fill="both", expand=True, padx=8)
        tree = ui.make_tree(holder, self.VISA_COLS, height=12)
        tree.tag_configure("expired", foreground="#a33")
        for r in rows:
            tree.insert("", "end", tags=("expired",) if r.expired else (),
                        values=(r.student_id, names.get(r.student_id, ""),
                                r.visa_type or "", r.visa_expiry,
                                r.days_left, "Expired" if r.expired
                                else "Expiring"))
        self.visa_tree = tree

    def _id(self) -> None:
        sid = self._sid()
        if not sid:
            return
        cur = idc.get_check(sid)
        initial = {"checked_by": ui.current_username() or ""}
        if cur is not None:
            for key, val in (("document_type", cur.id_document_type),
                             ("right_to_study", cur.right_to_study),
                             ("visa_type", cur.visa_type),
                             ("visa_expiry", cur.visa_expiry)):
                if val:
                    initial[key] = val
        fields = [
            ("document_type", "Document type", "readonly",
             idc.ID_DOCUMENT_TYPES),
            ("document_number", "Document number (only last 4 kept)",
             "entry", None),
            ("checked_by", "Checked by", "entry", None),
            ("checked_on", "Checked on (blank = today)", "entry", None)]
        if self.see:
            fields += [
                ("right_to_study", "Right to study", "readonly",
                 ["", *applicant_details.RIGHT_TO_STUDY]),
                ("visa_type", "Visa type (if any)", "entry", None),
                ("visa_expiry", "Visa expiry (YYYY-MM-DD)", "entry", None)]
        else:
            for key in ("right_to_study", "visa_type", "visa_expiry"):
                initial.pop(key, None)
        fields.append(("notes", "Notes", "text", None))
        if ui.ask_form(self.parent, f"ID check — {sid}", fields, initial,
                       on_submit=lambda v: idc.record_id_check(sid, **v)):
            self.refresh()

    def _history(self) -> None:
        sid = self._sid()
        if not sid:
            return
        try:
            rows = idc.id_history(sid)
        except Exception as e:  # noqa: BLE001 — AccessDenied shown plainly
            messagebox.showerror("ID history", describe_error(e),
                                 parent=self.parent)
            return
        win = make_toplevel(self.parent)
        win.title(f"ID check history — {sid}")
        win.geometry("1100x420")
        ttk.Button(win, text="Close", command=win.destroy).pack(
            side="bottom", anchor="e", padx=8, pady=8)
        ttk.Label(win, foreground="#555", text=(
            f"{len(rows)} check(s) recorded, newest first.")).pack(
            anchor="w", padx=8, pady=(8, 2))
        holder = ttk.Frame(win)
        holder.pack(fill="both", expand=True, padx=8)
        tree = ui.make_tree(holder, self.HIST_COLS, height=12)
        for r in rows:
            tree.insert("", "end", values=(
                r.get("id_checked_on") or "", r.get("id_document_type") or "",
                r.get("id_number_last4") or "", r.get("right_to_study") or "",
                r.get("visa_type") or "", r.get("visa_expiry") or "",
                r.get("id_checked_by") or "", r.get("source") or "",
                r.get("at") or ""))


def open_identity_checks_window(parent=None, student_id: str | None = None
                                ) -> None:
    win = ui.new_window(parent, "Enrolment photo & ID checks")
    IdentityChecksPanel(win, student_id=student_id)
