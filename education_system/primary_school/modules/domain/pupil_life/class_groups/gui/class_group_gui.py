"""Class group management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.class_groups.services.class_group_service import ClassGroupService
import traceback


class ClassGroupFrame(tk.Frame):
    """Main class group management screen with two-pane layout."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = ClassGroupService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Class Groups", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Assign Pupil", command=self._on_assign_pupil).pack(side="left", padx=3)
        tk.Button(toolbar, text="Remove Pupil", command=self._on_remove_pupil).pack(side="left", padx=3)

        # Main panes
        pane = tk.PanedWindow(self, orient="horizontal", sashwidth=5)
        pane.pack(fill="both", expand=True, padx=5, pady=5)

        # Left pane - class list
        left_frame = tk.Frame(pane)
        pane.add(left_frame, minsize=200)

        tk.Label(left_frame, text="Classes", font=("Helvetica", 11, "bold"),
                 anchor="w").pack(fill="x", padx=5, pady=2)

        list_frame = tk.Frame(left_frame)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._class_listbox = tk.Listbox(list_frame, width=30)
        self._class_listbox.pack(side="left", fill="both", expand=True)
        vsb_left = ttk.Scrollbar(list_frame, orient="vertical", command=self._class_listbox.yview)
        self._class_listbox.configure(yscrollcommand=vsb_left.set)
        vsb_left.pack(side="right", fill="y")
        self._class_listbox.bind("<<ListboxSelect>>", self._on_class_selected)

        # Right pane - pupils in selected class
        right_frame = tk.Frame(pane)
        pane.add(right_frame, minsize=400)

        tk.Label(right_frame, text="Pupils in Class", font=("Helvetica", 11, "bold"),
                 anchor="w").pack(fill="x", padx=5, pady=2)

        columns = ("pupil_id", "first_name", "last_name", "year_group")
        tree_frame = tk.Frame(right_frame)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        self._tree.column("pupil_id", width=80)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_classes()

    def refresh(self):
        self._load_classes()

    def _load_classes(self):
        self._class_listbox.delete(0, tk.END)
        try:
            classes = self._service.list_classes_with_counts()
            for c in classes:
                name = c.get("class_name", c.get("name", ""))
                count = c.get("pupil_count", 0)
                self._class_listbox.insert(tk.END, f"{name} ({count})")
            self._status_var.set(f"{len(classes)} class(es) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load classes: {e}")

    def _get_selected_class_name(self):
        sel = self._class_listbox.curselection()
        if not sel:
            return None
        text = self._class_listbox.get(sel[0])
        # Strip the count suffix " (N)"
        return text.rsplit(" (", 1)[0] if " (" in text else text

    def _on_class_selected(self, event=None):
        class_name = self._get_selected_class_name()
        if not class_name:
            return
        self._load_pupils(class_name)

    def _load_pupils(self, class_name):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            pupils = self._service.get_class_pupils(class_name)
            for p in pupils:
                pid = p.get("pupil_id", p.get("id"))
                self._tree.insert("", tk.END, iid=pid, values=(
                    pid, p.get("first_name", ""), p.get("last_name", ""),
                    p.get("year_group", ""),
                ))
            self._status_var.set(f"{len(pupils)} pupil(s) in {class_name}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load pupils: {e}")

    def _on_assign_pupil(self):
        class_name = self._get_selected_class_name()
        if not class_name:
            messagebox.showwarning("Selection", "Please select a class first.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Assign Pupil to Class")
        dlg.geometry("300x120")
        dlg.resizable(False, False)
        dlg.grab_set()

        frm = tk.Frame(dlg)
        frm.pack(fill="x", padx=10, pady=10)
        tk.Label(frm, text="Pupil ID:", width=12, anchor="w").pack(side="left")
        pupil_entry = tk.Entry(frm, width=20)
        pupil_entry.pack(side="left", fill="x", expand=True)

        def save():
            pupil_id = pupil_entry.get().strip()
            if not pupil_id:
                messagebox.showwarning("Validation", "Enter a Pupil ID.", parent=dlg)
                return
            try:
                self._service.assign_pupil_to_class(pupil_id, class_name)
                dlg.destroy()
                self._load_classes()
                self._load_pupils(class_name)
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill="x", pady=5, padx=10)
        tk.Button(btn_frame, text="Assign", command=save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy, width=12).pack(side="right", padx=5)

        dlg.transient(self)
        dlg.wait_visibility()
        dlg.grab_set()

    def _on_remove_pupil(self):
        class_name = self._get_selected_class_name()
        if not class_name:
            messagebox.showwarning("Selection", "Please select a class first.")
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a pupil first.")
            return
        pupil_id = sel[0]
        if not messagebox.askyesno("Confirm", f"Remove pupil {pupil_id} from {class_name}?"):
            return
        try:
            self._service.remove_pupil_from_class(pupil_id)
            self._load_classes()
            self._load_pupils(class_name)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
