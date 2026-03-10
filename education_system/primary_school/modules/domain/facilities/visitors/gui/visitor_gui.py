"""Visitor management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService
import traceback


class _VisitorDialog(tk.Toplevel):
    """Sign in visitor dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Sign In Visitor")
        self.geometry("450x380")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("visitor_name", "Visitor Name *")
        self._add_field("organisation", "Organisation")
        self._add_field("purpose", "Purpose *")
        self._add_field("visiting", "Visiting (staff name)")
        self._add_check("dbs_checked", "DBS Checked")
        self._add_check("safeguarding_briefing", "Safeguarding Briefing Given")
        self._add_field("badge_number", "Badge Number")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Sign In", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_check(self, key, label, default=False):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(frm, text=label, variable=var).pack(anchor="w")
        self._entries[key] = var

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, tk.BooleanVar):
                data[key] = int(widget.get())
            else:
                data[key] = widget.get().strip()
        if not data.get("visitor_name"):
            messagebox.showwarning("Validation", "Visitor name is required.", parent=self)
            return
        if not data.get("purpose"):
            messagebox.showwarning("Validation", "Purpose is required.", parent=self)
            return
        self.result = data
        self.destroy()


class VisitorFrame(tk.Frame):
    """Main visitor management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = VisitorService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Visitor Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Sign In", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Sign Out", command=self._on_sign_out).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Current Visitors", command=self._on_current_visitors).pack(side="left", padx=3)

        # Treeview
        columns = ("visitor_id", "visitor_name", "organisation", "purpose",
                   "visiting", "visit_date", "sign_in_time", "sign_out_time")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("visitor_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._show_current = False
        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            records = self._service.list_visitors()
            if self._show_current:
                records = [r for r in records if not r.get("sign_out_time")]
            for r in records:
                rid = r.get("visitor_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("visitor_name", ""), r.get("organisation", ""),
                    r.get("purpose", ""), r.get("visiting", ""),
                    r.get("visit_date", ""), r.get("sign_in_time", ""),
                    r.get("sign_out_time", ""),
                ))
            label = "current " if self._show_current else ""
            self._status_var.set(f"{len(records)} {label}visitor(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load visitors: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a visitor first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _VisitorDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.sign_in(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_sign_out(self):
        rid = self._selected_id()
        if not rid:
            return
        try:
            self._service.sign_out(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete visitor record {rid}?"):
            return
        try:
            self._service.delete_visitor(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_current_visitors(self):
        self._show_current = not self._show_current
        self._load_items()
