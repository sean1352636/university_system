"""Parents Evening GUI for managing evenings and booking slots."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.parents_evening.services.parents_evening_service import ParentsEveningService


class ParentsEveningFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ParentsEveningService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Parents Evening", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._evenings_tab = tk.Frame(self._nb)
        self._nb.add(self._evenings_tab, text="Evenings")
        self._build_evenings_tab()

        self._slots_tab = tk.Frame(self._nb)
        self._nb.add(self._slots_tab, text="Slots & Bookings")
        self._build_slots_tab()

    def _build_evenings_tab(self):
        toolbar = tk.Frame(self._evenings_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_evenings).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Evening", command=self._new_evening).pack(side="right", padx=5)

        cols = ("id", "title", "date", "start", "end", "slot_mins", "status")
        self._eve_tree = ttk.Treeview(self._evenings_tab, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 200, 100, 70, 70, 70, 80)):
            self._eve_tree.heading(c, text=c.replace("_", " ").title())
            self._eve_tree.column(c, width=w)
        self._eve_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_slots_tab(self):
        toolbar = tk.Frame(self._slots_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text="Evening ID:").pack(side="left", padx=5)
        self._slot_eid = tk.Entry(toolbar, width=8)
        self._slot_eid.pack(side="left", padx=5)
        ttk.Button(toolbar, text="Load Slots", command=self._load_slots).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Add Slot", command=self._new_slot).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Book Slot", command=self._book_slot).pack(side="right", padx=5)

        cols = ("id", "teacher", "time", "status", "parent", "student")
        self._slot_tree = ttk.Treeview(self._slots_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 80, 80, 100, 100)):
            self._slot_tree.heading(c, text=c.title())
            self._slot_tree.column(c, width=w)
        self._slot_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_evenings(self):
        for item in self._eve_tree.get_children():
            self._eve_tree.delete(item)
        try:
            evenings = self._svc.list_evenings()
            for e in evenings:
                self._eve_tree.insert("", "end", values=(
                    e["id"], e.get("title", ""), e.get("event_date", ""),
                    e.get("start_time", ""), e.get("end_time", ""),
                    e.get("slot_duration_mins", ""), e.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_slots(self):
        for item in self._slot_tree.get_children():
            self._slot_tree.delete(item)
        try:
            eid = self._slot_eid.get().strip()
            if not eid:
                return
            slots = self._svc.list_slots(int(eid))
            for s in slots:
                self._slot_tree.insert("", "end", iid=str(s["id"]), values=(
                    s["id"], s.get("teacher_name", s.get("teacher_id", "")),
                    s.get("slot_time", ""), s.get("status", ""),
                    s.get("parent_user_id", ""), s.get("student_id", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_evening(self):
        win = tk.Toplevel(self)
        win.title("New Parents Evening")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Title*:", "title"), ("Date* (YYYY-MM-DD):", "event_date"),
                           ("Start Time:", "start_time"), ("End Time:", "end_time"),
                           ("Slot Duration (mins):", "slot_duration_mins")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        fields["start_time"].insert(0, "16:00")
        fields["end_time"].insert(0, "20:00")
        fields["slot_duration_mins"].insert(0, "5")

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None
                dm = fields["slot_duration_mins"].get().strip()
                self._svc.create_evening(
                    title=fields["title"].get().strip(),
                    event_date=fields["event_date"].get().strip(),
                    start_time=fields["start_time"].get().strip() or "16:00",
                    end_time=fields["end_time"].get().strip() or "20:00",
                    slot_duration_mins=int(dm) if dm else 5,
                    created_by=user_id)
                messagebox.showinfo("Success", "Evening created")
                win.destroy()
                self._load_evenings()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _new_slot(self):
        win = tk.Toplevel(self)
        win.title("Add Slot")
        win.geometry("300x200")
        fields = {}
        row = 0
        for label, key in [("Evening ID*:", "evening_id"), ("Teacher ID*:", "teacher_id"),
                           ("Time* (HH:MM):", "slot_time")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=20)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.create_slot(
                    evening_id=int(fields["evening_id"].get().strip()),
                    teacher_id=int(fields["teacher_id"].get().strip()),
                    slot_time=fields["slot_time"].get().strip())
                messagebox.showinfo("Success", "Slot created")
                win.destroy()
                self._load_slots()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _book_slot(self):
        sel = self._slot_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a slot to book")
            return
        slot_id = int(sel[0])
        win = tk.Toplevel(self)
        win.title("Book Slot")
        win.geometry("300x150")
        fields = {}
        row = 0
        for label, key in [("Parent User ID*:", "parent_user_id"), ("Student ID*:", "student_id")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=20)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        def save():
            try:
                self._svc.book_slot(
                    slot_id, int(fields["parent_user_id"].get().strip()),
                    int(fields["student_id"].get().strip()))
                messagebox.showinfo("Success", "Slot booked")
                win.destroy()
                self._load_slots()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Book", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_evenings()
