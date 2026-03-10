"""Cover management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.staff.cover.services.cover_service import CoverService, COVER_STATUSES

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class CoverFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = CoverService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Cover Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Cover", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Assign Teacher", command=self._on_assign).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Complete", command=self._on_complete).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("date", "period", "absent", "cover", "year", "room", "work_set", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("date", "Date", 85), ("period", "P", 30), ("absent", "Absent Teacher", 120),
                           ("cover", "Cover Teacher", 120), ("year", "Year", 40), ("room", "Room", 55),
                           ("work_set", "Work Set", 150), ("status", "Status", 65)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        try:
            covers = self._svc.list_covers()
            for c in covers:
                self._tree.insert("", "end", iid=c["id"], values=(
                    c["date"], c["period"], c["absent_teacher"],
                    c.get("cover_teacher") or "UNASSIGNED", c.get("year_group") or "",
                    c.get("room") or "", c.get("work_set") or "", c["status"]))
            self._status_var.set(f"{len(covers)} cover lesson(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Cover Lesson")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        for row, (l, k, d) in enumerate([("Absent Teacher", "absent_teacher", ""),
                                           ("Date (YYYY-MM-DD)", "date", ""),
                                           ("Period (1-6)", "period", "1"),
                                           ("Cover Teacher", "cover_teacher", ""),
                                           ("Year Group", "year_group", ""),
                                           ("Room", "room", ""),
                                           ("Work Set", "work_set", "")]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            at = vars_["absent_teacher"].get().strip()
            dt = vars_["date"].get().strip()
            if not at or not dt:
                messagebox.showwarning("Validation", "Absent teacher and date required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=7, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            p = int(d["period"]) if d["period"] else 1
        except ValueError:
            p = 1
        self._svc.create_cover(d["absent_teacher"], d["date"], p,
                               d["cover_teacher"] or None, year_group=d["year_group"] or None,
                               room=d["room"] or None, work_set=d["work_set"] or None)
        self._load()

    def _on_assign(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a cover lesson.")
            return
        from tkinter import simpledialog
        teacher = simpledialog.askstring("Assign Cover", "Cover teacher name:")
        if teacher:
            self._svc.assign_cover(int(sel[0]), teacher.strip())
            self._load()

    def _on_complete(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.complete_cover(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this cover lesson?"):
            self._svc.delete_cover(int(sel[0]))
            self._load()
