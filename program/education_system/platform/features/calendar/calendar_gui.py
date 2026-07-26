"""GUI frame for the Cross-System Calendar."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.platform.features.calendar.calendar_service import (
    CrossSystemCalendarService,
    EVENT_TYPES,
)

SYSTEM_NAMES = {
    "university": "University",
    "sixth_form": "Sixth Form College",
    "secondary": "Secondary School",
    "primary": "Primary School",
}

ALL_SYSTEMS_KEYS = ["primary", "secondary", "sixth_form", "university"]


class CrossSystemCalendarFrame(tk.Frame):
    """Frame for viewing and managing cross-system calendar events."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CrossSystemCalendarService(db_path=db_path)
        self._build_ui()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_user_name(self):
        if isinstance(self._auth, dict):
            return self._auth.get("display_name") or self._auth.get("username", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("display_name") or self._auth.current_user.get("username", "")
        return ""

    def _get_system(self):
        if isinstance(self._auth, dict):
            return self._auth.get("system_key", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("system_key", "")
        return ""

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Cross-System Calendar",
            font=("Helvetica", 15, "bold"), bg="#1a5276", fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Toolbar: month/year selector + filters
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        now = datetime.now()
        ttk.Label(toolbar, text="Month:").pack(side="left", padx=(0, 4))
        self._month_var = tk.StringVar(value=str(now.month))
        ttk.Combobox(
            toolbar, textvariable=self._month_var,
            values=[str(m) for m in range(1, 13)],
            state="readonly", width=4,
        ).pack(side="left", padx=2)

        ttk.Label(toolbar, text="Year:").pack(side="left", padx=(8, 4))
        self._year_var = tk.StringVar(value=str(now.year))
        ttk.Combobox(
            toolbar, textvariable=self._year_var,
            values=[str(y) for y in range(now.year - 1, now.year + 3)],
            state="readonly", width=6,
        ).pack(side="left", padx=2)

        ttk.Label(toolbar, text="Type:").pack(side="left", padx=(12, 4))
        self._type_filter = tk.StringVar(value="All")
        ttk.Combobox(
            toolbar, textvariable=self._type_filter,
            values=["All"] + list(EVENT_TYPES),
            state="readonly", width=12,
        ).pack(side="left", padx=2)

        ttk.Label(toolbar, text="System:").pack(side="left", padx=(12, 4))
        self._system_filter = tk.StringVar(value="All")
        ttk.Combobox(
            toolbar, textvariable=self._system_filter,
            values=["All"] + ALL_SYSTEMS_KEYS,
            state="readonly", width=12,
        ).pack(side="left", padx=2)

        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left", padx=8)

        # Buttons
        btn_bar = tk.Frame(self, bg="#ecf0f1")
        btn_bar.pack(fill="x", padx=15, pady=(0, 5))
        ttk.Button(btn_bar, text="Add Event", command=self._add_event_dialog).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Edit", command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Delete", command=self._delete_selected).pack(side="left", padx=4)

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("date", "time", "title", "type", "systems", "created_by")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse",
        )
        for col, heading, width in [
            ("date", "Date", 100),
            ("time", "Time", 70),
            ("title", "Title", 220),
            ("type", "Type", 100),
            ("systems", "Systems", 150),
            ("created_by", "Created By", 130),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center" if col in ("date", "time", "type") else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Stored event data keyed by treeview iid
        self._event_data = {}

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload events for the selected month/year with optional filters."""
        self._tree.delete(*self._tree.get_children())
        self._event_data.clear()

        month = self._month_var.get()
        year = self._year_var.get()
        sys_filter = self._system_filter.get()
        type_filter = self._type_filter.get()

        system = sys_filter if sys_filter != "All" else None

        try:
            events = self._svc.get_events(system=system, month=month, year=year)

            if type_filter != "All":
                events = [e for e in events if e.get("event_type") == type_filter]

            for ev in events:
                iid = str(ev["id"])
                systems_display = ev.get("systems", "all")
                if systems_display != "all":
                    parts = [SYSTEM_NAMES.get(s.strip(), s.strip()) for s in systems_display.split(",")]
                    systems_display = ", ".join(parts)
                else:
                    systems_display = "All Systems"

                self._tree.insert("", "end", iid=iid, values=(
                    ev.get("event_date", ""),
                    ev.get("event_time", ""),
                    ev.get("title", ""),
                    ev.get("event_type", ""),
                    systems_display,
                    ev.get("created_by", ""),
                ))
                self._event_data[iid] = ev
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ------------------------------------------------------------------
    # add / edit / delete
    # ------------------------------------------------------------------

    def _add_event_dialog(self):
        self._event_dialog(mode="add")

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an event to edit.", parent=self)
            return
        ev = self._event_data.get(sel[0])
        if ev:
            self._event_dialog(mode="edit", event=ev)

    def _event_dialog(self, mode="add", event=None):
        dlg = tk.Toplevel(self)
        dlg.title("Add Event" if mode == "add" else "Edit Event")
        dlg.geometry("480x520")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        frm = tk.Frame(dlg, padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        pad = {"padx": 8, "pady": 4}
        row = 0

        # Title
        tk.Label(frm, text="Title:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", **pad)
        title_var = tk.StringVar(value=event.get("title", "") if event else "")
        ttk.Entry(frm, textvariable=title_var, width=35).grid(row=row, column=1, **pad)
        row += 1

        # Description
        tk.Label(frm, text="Description:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="nw", **pad)
        desc_text = tk.Text(frm, height=4, width=35, font=("Helvetica", 10))
        desc_text.grid(row=row, column=1, **pad)
        if event and event.get("description"):
            desc_text.insert("1.0", event["description"])
        row += 1

        # Date
        tk.Label(frm, text="Date (YYYY-MM-DD):", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", **pad)
        date_var = tk.StringVar(value=event.get("event_date", "") if event else datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frm, textvariable=date_var, width=15).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Time
        tk.Label(frm, text="Time (HH:MM):", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", **pad)
        time_var = tk.StringVar(value=event.get("event_time", "") if event else "")
        ttk.Entry(frm, textvariable=time_var, width=10).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # End date
        tk.Label(frm, text="End Date:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", **pad)
        end_var = tk.StringVar(value=event.get("end_date", "") if event else "")
        ttk.Entry(frm, textvariable=end_var, width=15).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Event type
        tk.Label(frm, text="Event Type:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="w", **pad)
        type_var = tk.StringVar(value=event.get("event_type", "other") if event else "other")
        ttk.Combobox(frm, textvariable=type_var, values=list(EVENT_TYPES), state="readonly", width=15).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Systems checkboxes
        tk.Label(frm, text="Systems:", font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky="nw", **pad)
        sys_frame = tk.Frame(frm)
        sys_frame.grid(row=row, column=1, sticky="w", **pad)

        existing_systems = set()
        if event and event.get("systems"):
            if event["systems"] == "all":
                existing_systems = set(ALL_SYSTEMS_KEYS)
            else:
                existing_systems = {s.strip() for s in event["systems"].split(",")}

        sys_vars = {}
        for skey in ALL_SYSTEMS_KEYS:
            var = tk.BooleanVar(value=skey in existing_systems or (not event))
            cb = ttk.Checkbutton(sys_frame, text=SYSTEM_NAMES.get(skey, skey), variable=var)
            cb.pack(anchor="w")
            sys_vars[skey] = var
        row += 1

        def _save():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            date_val = date_var.get().strip()
            if not date_val:
                messagebox.showwarning("Validation", "Date is required.", parent=dlg)
                return

            desc = desc_text.get("1.0", "end").strip()
            time_val = time_var.get().strip()
            end_val = end_var.get().strip()
            etype = type_var.get()

            selected = [k for k, v in sys_vars.items() if v.get()]
            if not selected or len(selected) == len(ALL_SYSTEMS_KEYS):
                systems_str = "all"
            else:
                systems_str = ",".join(selected)

            try:
                if mode == "add":
                    self._svc.create_event(
                        title=title, description=desc, date=date_val,
                        time=time_val, end_date=end_val, systems=systems_str,
                        event_type=etype, created_by=self._get_user_name(),
                        created_system=self._get_system(),
                    )
                    messagebox.showinfo("Success", "Event created.", parent=dlg)
                else:
                    self._svc.update_event(
                        event["id"],
                        title=title, description=desc, event_date=date_val,
                        event_time=time_val, end_date=end_val,
                        systems=systems_str, event_type=etype,
                    )
                    messagebox.showinfo("Success", "Event updated.", parent=dlg)
                dlg.destroy()
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="Save", command=_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an event to delete.", parent=self)
            return

        ev = self._event_data.get(sel[0])
        if not ev:
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete event '{ev.get('title', '')}'?",
            parent=self,
        )
        if confirm:
            try:
                self._svc.delete_event(ev["id"])
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)
