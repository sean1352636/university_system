"""Homework management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
import traceback


HOMEWORK_STATUSES = ["All", "Draft", "Set", "Submitted", "Marked", "Overdue"]

STICKER_DISPLAY = {
    "gold_star": "Gold Star",
    "well_done": "Well Done",
    "good_effort": "Good Effort",
    "keep_trying": "Keep Trying",
}


class _HomeworkDialog(tk.Toplevel):
    """Add / Edit homework dialog."""

    def __init__(self, parent, db_path, homework=None):
        super().__init__(parent)
        self.result = None
        self._homework = homework
        self.title("Edit Homework" if homework else "Add Homework")
        self.geometry("480x400")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "title", "Title *")
        self._add_field(frm, "description", "Description")
        self._add_field(frm, "class_name", "Class Name *")
        self._add_field(frm, "subject_code", "Subject Code")
        self._add_field(frm, "due_date", "Due Date (YYYY-MM-DD) *")
        self._add_field(frm, "set_by", "Set By (Staff ID)")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if homework:
            for key, widget in self._entries.items():
                val = homework.get(key)
                if val is None:
                    continue
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_check(self, parent, key, label, default=False):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(frm, text=label, variable=var).pack(anchor="w")
        self._entries[key] = var

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, tk.BooleanVar):
                data[key] = int(widget.get())
            elif isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("class_name"):
            messagebox.showwarning("Validation", "Class name is required.", parent=self)
            return
        if not data.get("due_date"):
            messagebox.showwarning("Validation", "Due date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class HomeworkFrame(tk.Frame):
    """Main homework management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = HomeworkService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Homework Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Homework", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)
        tk.Button(toolbar, text="View Submissions", command=self._on_view_submissions).pack(side="left", padx=3)
        tk.Button(toolbar, text="Outstanding", command=self._on_outstanding).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Class:", bg="#d5dbdb").pack(side="left")
        self._class_filter = ttk.Combobox(toolbar, values=["All"], state="readonly", width=12)
        self._class_filter.set("All")
        self._class_filter.pack(side="left", padx=3)
        self._class_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left", padx=(5, 0))
        self._status_filter = ttk.Combobox(toolbar, values=HOMEWORK_STATUSES,
                                            state="readonly", width=10)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("title", "class_name", "subject", "set_date", "due_date", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        class_name = self._class_filter.get()
        class_name = None if class_name == "All" else class_name
        status = self._status_filter.get()
        status = None if status == "All" else status
        search = self._search_var.get().strip() or None
        try:
            items = self._service.list_homework(
                class_name=class_name, status=status
            )
            for h in items:
                self._tree.insert("", tk.END, iid=h.get("homework_id", ""), values=(
                    h.get("title", ""),
                    h.get("class_name", ""),
                    h.get("subject_code", h.get("subject", "")),
                    h.get("set_date", ""),
                    h.get("due_date", ""),
                    h.get("status", ""),
                ))
            self._status_var.set(f"{len(items)} homework item(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load homework: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._class_filter.set("All")
        self._status_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a homework item first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _HomeworkDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_homework(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        hid = self._selected_id()
        if not hid:
            return
        homework = self._service.get_homework(hid)
        if not homework:
            messagebox.showerror("Error", "Homework not found.")
            return
        dlg = _HomeworkDialog(self, self._db_path, homework=homework)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_homework(hid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        hid = self._selected_id()
        if not hid:
            return
        if not messagebox.askyesno("Confirm", f"Delete homework {hid}?"):
            return
        try:
            self._service.delete_homework(hid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    # ---- Submissions with feedback & stickers ----

    def _on_view_submissions(self):
        """View submissions for a homework item with feedback and sticker support."""
        hid = self._selected_id()
        if not hid:
            return
        subs = self._service.get_submissions(hid)
        dlg = tk.Toplevel(self)
        dlg.title("Submissions & Feedback")
        dlg.geometry("700x480")
        dlg.grab_set()

        notebook = ttk.Notebook(dlg)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Submissions list tab ---
        sub_frame = tk.Frame(notebook)
        notebook.add(sub_frame, text="Submissions")

        cols = ("id", "pupil", "submitted", "status", "sticker", "feedback")
        tree = ttk.Treeview(sub_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("id", "ID", 35), ("pupil", "Pupil", 140),
                           ("submitted", "Submitted", 100), ("status", "Status", 65),
                           ("sticker", "Sticker", 90), ("feedback", "Feedback", 150)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center" if col != "feedback" else "w")
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        for s in subs:
            # Load feedback for each submission
            fb = self._service.get_submission_with_feedback(s["id"])
            sticker_text = STICKER_DISPLAY.get(fb.get("sticker", ""), "") if fb else ""
            teacher_fb = (fb.get("teacher_feedback") or "")[:40] if fb else ""
            tree.insert("", "end", iid=s["id"], values=(
                s["id"],
                f"{s['first_name']} {s['last_name']}",
                s.get("submitted_date", ""),
                s.get("status", ""),
                sticker_text,
                teacher_fb))

        btn_row = tk.Frame(sub_frame)
        btn_row.pack(fill="x", padx=5, pady=5)

        def _on_add_teacher_feedback():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection", "Select a submission first.", parent=dlg)
                return
            sub_id = int(sel[0])
            fb_dlg = tk.Toplevel(dlg)
            fb_dlg.title("Teacher Feedback")
            fb_dlg.geometry("420x320")
            fb_dlg.grab_set()

            # Load existing feedback
            existing = self._service.get_submission_with_feedback(sub_id)

            tk.Label(fb_dlg, text="Feedback:", font=("Helvetica", 9, "bold")).pack(
                anchor="w", padx=10, pady=(10, 2))
            fb_text = tk.Text(fb_dlg, height=6, width=45)
            fb_text.pack(padx=10, pady=5)
            if existing and existing.get("teacher_feedback"):
                fb_text.insert("1.0", existing["teacher_feedback"])

            tk.Label(fb_dlg, text="Sticker:", font=("Helvetica", 9, "bold")).pack(
                anchor="w", padx=10, pady=(5, 2))
            sticker_var = tk.StringVar(value=existing.get("sticker", "") if existing else "")
            sticker_options = [""] + list(STICKER_DISPLAY.keys())
            sticker_combo = ttk.Combobox(fb_dlg, textvariable=sticker_var,
                                          values=sticker_options, state="readonly", width=20)
            sticker_combo.pack(anchor="w", padx=10, pady=2)

            def save():
                txt = fb_text.get("1.0", "end").strip()
                stk = sticker_var.get() or None
                if not txt:
                    messagebox.showwarning("Validation", "Feedback text is required.", parent=fb_dlg)
                    return
                try:
                    self._service.add_teacher_feedback(sub_id, txt, stk)
                    messagebox.showinfo("Success", "Feedback saved.", parent=fb_dlg)
                    fb_dlg.destroy()
                    # Refresh the submissions view
                    self._on_view_submissions_refresh(tree, hid)
                except Exception as e:
                    traceback.print_exc()
                    messagebox.showerror("Error", str(e), parent=fb_dlg)

            ttk.Button(fb_dlg, text="Save Feedback", command=save).pack(pady=10)

        def _on_add_parent_comment():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection", "Select a submission first.", parent=dlg)
                return
            sub_id = int(sel[0])
            pc_dlg = tk.Toplevel(dlg)
            pc_dlg.title("Parent Comment")
            pc_dlg.geometry("420x250")
            pc_dlg.grab_set()

            existing = self._service.get_submission_with_feedback(sub_id)

            tk.Label(pc_dlg, text="Parent ID:", font=("Helvetica", 9, "bold")).pack(
                anchor="w", padx=10, pady=(10, 2))
            pid_var = tk.StringVar(value=existing.get("parent_id", "") if existing else "")
            tk.Entry(pc_dlg, textvariable=pid_var, width=25).pack(anchor="w", padx=10, pady=2)

            tk.Label(pc_dlg, text="Comment:", font=("Helvetica", 9, "bold")).pack(
                anchor="w", padx=10, pady=(5, 2))
            comment_text = tk.Text(pc_dlg, height=4, width=45)
            comment_text.pack(padx=10, pady=5)
            if existing and existing.get("parent_comment"):
                comment_text.insert("1.0", existing["parent_comment"])

            def save():
                pid = pid_var.get().strip()
                cmt = comment_text.get("1.0", "end").strip()
                if not pid or not cmt:
                    messagebox.showwarning("Validation", "Parent ID and comment are required.", parent=pc_dlg)
                    return
                try:
                    self._service.add_parent_comment(sub_id, cmt, pid)
                    messagebox.showinfo("Success", "Parent comment saved.", parent=pc_dlg)
                    pc_dlg.destroy()
                    self._on_view_submissions_refresh(tree, hid)
                except Exception as e:
                    traceback.print_exc()
                    messagebox.showerror("Error", str(e), parent=pc_dlg)

            ttk.Button(pc_dlg, text="Save Comment", command=save).pack(pady=10)

        def _on_view_detail():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection", "Select a submission first.", parent=dlg)
                return
            sub_id = int(sel[0])
            detail = self._service.get_submission_with_feedback(sub_id)
            if not detail:
                messagebox.showinfo("Detail", "No data found.", parent=dlg)
                return
            det_dlg = tk.Toplevel(dlg)
            det_dlg.title(f"Submission Detail #{sub_id}")
            det_dlg.geometry("450x350")
            txt = tk.Text(det_dlg, wrap="word")
            txt.pack(fill="both", expand=True, padx=10, pady=10)
            txt.insert("end", f"Pupil: {detail['first_name']} {detail['last_name']}\n")
            txt.insert("end", f"Submitted: {detail.get('submitted_date', 'N/A')}\n")
            txt.insert("end", f"Status: {detail.get('status', 'N/A')}\n")
            if detail.get("file_path"):
                txt.insert("end", f"Attachment: {detail['file_path']}\n")
            txt.insert("end", f"\n--- Teacher Feedback ---\n")
            txt.insert("end", f"{detail.get('teacher_feedback') or 'None yet'}\n")
            sticker = detail.get("sticker")
            if sticker:
                txt.insert("end", f"Sticker: {STICKER_DISPLAY.get(sticker, sticker)}\n")
            txt.insert("end", f"\n--- Parent Comment ---\n")
            txt.insert("end", f"{detail.get('parent_comment') or 'None yet'}\n")
            if detail.get("parent_id"):
                txt.insert("end", f"(by parent: {detail['parent_id']})\n")
            txt.config(state="disabled")

        tk.Button(btn_row, text="Add Teacher Feedback", command=_on_add_teacher_feedback).pack(side="left", padx=3)
        tk.Button(btn_row, text="Add Parent Comment", command=_on_add_parent_comment).pack(side="left", padx=3)
        tk.Button(btn_row, text="View Detail", command=_on_view_detail).pack(side="left", padx=3)

    def _on_view_submissions_refresh(self, tree, hid):
        """Refresh the submissions treeview after a feedback update."""
        tree.delete(*tree.get_children())
        subs = self._service.get_submissions(hid)
        for s in subs:
            fb = self._service.get_submission_with_feedback(s["id"])
            sticker_text = STICKER_DISPLAY.get(fb.get("sticker", ""), "") if fb else ""
            teacher_fb = (fb.get("teacher_feedback") or "")[:40] if fb else ""
            tree.insert("", "end", iid=s["id"], values=(
                s["id"],
                f"{s['first_name']} {s['last_name']}",
                s.get("submitted_date", ""),
                s.get("status", ""),
                sticker_text,
                teacher_fb))

    # ---- Outstanding homework ----

    def _on_outstanding(self):
        """Show outstanding homework for a given pupil."""
        dlg = tk.Toplevel(self)
        dlg.title("Outstanding Homework")
        dlg.geometry("550x400")
        dlg.grab_set()

        top = tk.Frame(dlg)
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Pupil ID:", font=("Helvetica", 9, "bold")).pack(side="left")
        pid_var = tk.StringVar()
        tk.Entry(top, textvariable=pid_var, width=15).pack(side="left", padx=5)

        cols = ("title", "class_name", "subject", "due_date")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("title", "Title", 180), ("class_name", "Class", 90),
                           ("subject", "Subject", 90), ("due_date", "Due Date", 100)]:
            tree.heading(col, text=h)
            tree.column(col, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        status_var = tk.StringVar(value="Enter a pupil ID and click Search.")
        tk.Label(dlg, textvariable=status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        def search():
            pid = pid_var.get().strip()
            if not pid:
                messagebox.showwarning("Validation", "Pupil ID is required.", parent=dlg)
                return
            tree.delete(*tree.get_children())
            try:
                items = self._service.list_outstanding(pid)
                for h in items:
                    tree.insert("", "end", values=(
                        h.get("title", ""),
                        h.get("class_name", ""),
                        h.get("subject_code", ""),
                        h.get("due_date", "")))
                status_var.set(f"{len(items)} outstanding homework item(s)")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e), parent=dlg)

        tk.Button(top, text="Search", command=search).pack(side="left", padx=5)
