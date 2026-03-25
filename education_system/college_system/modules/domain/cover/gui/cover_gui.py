"""Cover GUI for managing substitution/cover arrangements."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.cover.services.cover_service import CoverService
from education_system.college_system.core.i18n import t


class CoverFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CoverService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("cover.management"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._today_tab = tk.Frame(self._nb)
        self._nb.add(self._today_tab, text=t("cover.management"))
        self._build_today_tab()

        self._all_tab = tk.Frame(self._nb)
        self._nb.add(self._all_tab, text=t("common.all"))
        self._build_all_tab()

    def _build_today_tab(self):
        toolbar = tk.Frame(self._today_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_today).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("cover.arrange_cover"), command=self._new_arrangement).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=5)

        cols = ("id", "absent", "cover", "period", "course", "room", "status")
        self._today_tree = ttk.Treeview(self._today_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 120, 60, 150, 80, 80)):
            self._today_tree.heading(c, text=c.title())
            self._today_tree.column(c, width=w)
        self._today_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self._detail_text = tk.Text(self._today_tab, height=4, state="disabled")
        self._detail_text.pack(fill="x", padx=5, pady=5)
        self._today_tree.bind("<<TreeviewSelect>>", self._on_today_select)

    def _build_all_tab(self):
        toolbar = tk.Frame(self._all_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text="Date:").pack(side="left", padx=5)
        self._date_entry = tk.Entry(toolbar, width=12)
        self._date_entry.pack(side="left", padx=5)
        tk.Label(toolbar, text="Status:").pack(side="left", padx=5)
        self._status_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._status_var,
                      values=["All", "pending", "confirmed", "completed", "cancelled"],
                      state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.filter"), command=self._load_all).pack(side="left", padx=5)

        cols = ("id", "date", "absent", "cover", "period", "course", "room", "status")
        self._all_tree = ttk.Treeview(self._all_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 100, 120, 120, 60, 150, 80, 80)):
            self._all_tree.heading(c, text=c.title())
            self._all_tree.column(c, width=w)
        self._all_tree.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(self._all_tab)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text=t("common.update"), command=self._update_arrangement).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.delete"), command=self._delete_arrangement).pack(side="left", padx=5)

    def _load_today(self):
        for item in self._today_tree.get_children():
            self._today_tree.delete(item)
        try:
            arrangements = self._svc.get_today_cover()
            for a in arrangements:
                self._today_tree.insert("", "end", iid=str(a["id"]), values=(
                    a["id"], a.get("absent_staff_name", ""),
                    a.get("cover_staff_name", ""), a.get("period", ""),
                    a.get("course_name", ""), a.get("room", ""),
                    a.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_today_select(self, _event=None):
        sel = self._today_tree.selection()
        if not sel:
            return
        try:
            arr = self._svc.get_arrangement(int(sel[0]))
            self._detail_text.configure(state="normal")
            self._detail_text.delete("1.0", "end")
            self._detail_text.insert("end", f"Reason: {arr.get('reason', '')}\n")
            self._detail_text.insert("end", f"Work Set: {arr.get('work_set', '')}\n")
            self._detail_text.insert("end", f"Notes: {arr.get('notes', '')}")
            self._detail_text.configure(state="disabled")
        except Exception:
            pass

    def _load_all(self):
        for item in self._all_tree.get_children():
            self._all_tree.delete(item)
        try:
            date_val = self._date_entry.get().strip()
            status = self._status_var.get()
            arrangements = self._svc.list_arrangements(
                cover_date=date_val if date_val else None,
                status=None if status == "All" else status)
            for a in arrangements:
                self._all_tree.insert("", "end", iid=str(a["id"]), values=(
                    a["id"], a.get("cover_date", ""),
                    a.get("absent_staff_name", ""),
                    a.get("cover_staff_name", ""), a.get("period", ""),
                    a.get("course_name", ""), a.get("room", ""),
                    a.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_arrangement(self):
        win = tk.Toplevel(self)
        win.title(t("cover.arrange_cover"))
        win.geometry("400x400")
        fields = {}
        row = 0
        for label, key in [("Absent Staff ID*:", "absent_staff_id"),
                           ("Cover Staff ID:", "cover_staff_id"),
                           ("Date (YYYY-MM-DD):", "cover_date"),
                           ("Period:", "period"), ("Course ID:", "course_id"),
                           ("Room:", "room"), ("Reason:", "reason")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1
        tk.Label(win, text="Work Set:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        work_set = tk.Text(win, width=30, height=3)
        work_set.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                cover_id = fields["cover_staff_id"].get().strip()
                course_id = fields["course_id"].get().strip()
                self._svc.create_arrangement(
                    absent_staff_id=int(fields["absent_staff_id"].get().strip()),
                    cover_staff_id=int(cover_id) if cover_id else None,
                    cover_date=fields["cover_date"].get().strip() or None,
                    period=fields["period"].get().strip() or None,
                    course_id=int(course_id) if course_id else None,
                    room=fields["room"].get().strip() or None,
                    reason=fields["reason"].get().strip() or None,
                    work_set=work_set.get("1.0", "end").strip() or None)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_today()
                self._load_all()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _update_arrangement(self):
        sel = self._all_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        arr_id = int(sel[0])
        win = tk.Toplevel(self)
        win.title(t("common.update"))
        win.geometry("350x200")
        tk.Label(win, text="Cover Staff ID:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        cover_entry = tk.Entry(win, width=20)
        cover_entry.grid(row=0, column=1, padx=10, pady=5)
        tk.Label(win, text="Status:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value="confirmed")
        ttk.Combobox(win, textvariable=status_var,
                      values=["pending", "confirmed", "completed", "cancelled"],
                      state="readonly", width=17).grid(row=1, column=1, padx=10, pady=5)
        tk.Label(win, text="Room:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        room_entry = tk.Entry(win, width=20)
        room_entry.grid(row=2, column=1, padx=10, pady=5)

        def save():
            try:
                kwargs = {"status": status_var.get()}
                ci = cover_entry.get().strip()
                rm = room_entry.get().strip()
                if ci:
                    kwargs["cover_staff_id"] = int(ci)
                if rm:
                    kwargs["room"] = rm
                self._svc.update_arrangement(arr_id, **kwargs)
                win.destroy()
                self._load_all()
                self._load_today()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def _delete_arrangement(self):
        sel = self._all_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            try:
                self._svc.delete_arrangement(int(sel[0]))
                self._load_all()
                self._load_today()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._today_tree, "cover.csv")

    def refresh(self):
        self._load_today()
