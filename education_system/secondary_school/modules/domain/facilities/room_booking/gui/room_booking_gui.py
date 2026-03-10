"""Room Booking GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class RoomBookingFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = RoomBookingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Room Booking", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Book Room", command=self._on_book).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Cancel Booking", command=self._on_cancel).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("room", "date", "start", "end", "purpose", "booked_by", "equipment", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("room", "Room", 80), ("date", "Date", 85), ("start", "Start", 55),
                           ("end", "End", 55), ("purpose", "Purpose", 160),
                           ("booked_by", "Booked By", 90), ("equipment", "Equipment", 110),
                           ("status", "Status", 65)]:
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
            bookings = self._svc.list_bookings()
            for b in bookings:
                self._tree.insert("", "end", iid=b["id"], values=(
                    b["room"], b["date"], b["start_time"], b["end_time"],
                    b["purpose"], b.get("booked_by") or "",
                    b.get("equipment_needed") or "", b["status"]))
            self._status_var.set(f"{len(bookings)} booking(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_book(self):
        dlg = tk.Toplevel(self)
        dlg.title("Book Room")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Room", "room", ""), ("Date (YYYY-MM-DD)", "date", ""),
                  ("Start Time (HH:MM)", "start", ""), ("End Time (HH:MM)", "end", ""),
                  ("Purpose", "purpose", ""), ("Equipment Needed", "equipment", "")]
        for row, (l, k, d) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=22).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            rm = vars_["room"].get().strip()
            dt = vars_["date"].get().strip()
            st = vars_["start"].get().strip()
            et = vars_["end"].get().strip()
            pu = vars_["purpose"].get().strip()
            if not rm or not dt or not st or not et or not pu:
                messagebox.showwarning("Validation", "Room, date, times and purpose required.")
                return
            result[0] = {"room": rm, "date": dt, "start": st, "end": et, "purpose": pu,
                         "equipment": vars_["equipment"].get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Book", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        booked_by = self._auth.get("username") if self._auth else None
        try:
            self._svc.book_room(d["room"], d["date"], d["start"], d["end"],
                                d["purpose"], booked_by, d["equipment"])
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_cancel(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.cancel_booking(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this booking?"):
            self._svc.delete_booking(int(sel[0]))
            self._load()
