"""Standalone Tk app: Building Management.

Eight integrated subsystems, each surfaced as a Notebook tab:
  1. Buildings — registry (table: ``buildings``)
  2. Rooms — room inventory (table: ``rooms``)
  3. Utilities — electricity / water / gas readings (table: ``energy_usage``)
  4. Cleaning — recurring cleaning schedules (table: ``bm_cleaning_schedules``)
  5. Maintenance — work orders (table: ``maintenance_requests``)
  6. Occupancy — occupant counts + utilisation (table: ``bm_occupancy_records``)
  7. Access Cards — keycard / access management (table: ``access_cards``)
  8. Inspections — lift / fire / regulatory (table: ``housing_inspections``)

Persistence: writes to the central ``data/db_files/student_records.db``.
Existing tables are reused as-is; only the two ``bm_``-prefixed tables
are created here, and only via ``CREATE TABLE IF NOT EXISTS``.

Auth: piggybacks on the unified GUI auth via EDU_AUTH_* env vars when
launched as a subprocess. Falls back to in-process global auth.

Logging: routed through the shared rotating ``app.log`` if available;
otherwise to stderr at INFO.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    configure_logging(name=__name__)
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.debug("Central log config unavailable; using stderr fallback",
                 exc_info=True)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get("EDU_AUTH_USER_ID") or ""
    username = os.environ.get("EDU_AUTH_USERNAME") or ""
    role = os.environ.get("EDU_AUTH_ROLE") or ""
    email = os.environ.get("EDU_AUTH_EMAIL") or ""
    perms_raw = os.environ.get("EDU_AUTH_PERMISSIONS") or ""
    if user_id or username:
        return {
            "id": user_id or None,
            "username": username,
            "role": role,
            "email": email,
            "permissions": [p for p in perms_raw.split(",") if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import (
            get_global_auth,
        )
        ga = get_global_auth()
        if ga and getattr(ga, "current_user", None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return "Guest"
    return (user.get("username") or user.get("email")
            or user.get("id") or "Unknown")


# ---------------------------------------------------------------------------
# Database (uses the central student_records.db)
# ---------------------------------------------------------------------------
def _resolve_db_path() -> pathlib.Path:
    repo_root = pathlib.Path(__file__).resolve()
    while (repo_root.parent != repo_root
           and not (repo_root / "education_system").is_dir()):
        repo_root = repo_root.parent
    db_dir = (repo_root / "education_system" / "university_system"
              / "data" / "db_files")
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "student_records.db"


DB_PATH = _resolve_db_path()


# Only create the tables we own — everything else is pre-existing.
NEW_TABLES = [
    """CREATE TABLE IF NOT EXISTS bm_cleaning_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        building_id INTEGER NOT NULL,
        room_id INTEGER,
        frequency TEXT NOT NULL,
        last_cleaned TEXT,
        next_due TEXT,
        assigned_to TEXT,
        status TEXT DEFAULT 'scheduled',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS bm_occupancy_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        building_id INTEGER NOT NULL,
        room_id INTEGER,
        timestamp TEXT NOT NULL,
        occupant_count INTEGER NOT NULL,
        capacity INTEGER NOT NULL,
        utilization_pct REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
]


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    try:
        with get_conn() as conn:
            for stmt in NEW_TABLES:
                conn.execute(stmt)
        logger.info("building_management ready (db=%s)", DB_PATH)
    except Exception:
        logger.exception("init_db failed")
        raise


def _fetch_all(query, params=()):
    try:
        with get_conn() as conn:
            return conn.execute(query, params).fetchall()
    except Exception:
        logger.exception("fetch_all failed: %s", query)
        return []


def _exec(query, params=()):
    try:
        with get_conn() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        logger.warning("integrity error: %s", e)
        raise
    except Exception:
        logger.exception("exec failed: %s", query)
        raise


def buildings_for_picker():
    rows = _fetch_all(
        "SELECT building_id, building_name, building_code FROM buildings "
        "WHERE COALESCE(is_active,1)=1 ORDER BY building_code")
    return [(r["building_id"],
             f"{r['building_code']} — {r['building_name']}") for r in rows]


def rooms_for_picker(building_id=None):
    if building_id:
        rows = _fetch_all(
            "SELECT id, room_number, COALESCE(floor_number,0) AS floor "
            "FROM rooms WHERE building_id=? AND COALESCE(is_active,1)=1 "
            "ORDER BY floor, room_number", (building_id,))
    else:
        rows = _fetch_all(
            "SELECT id, room_number, COALESCE(floor_number,0) AS floor "
            "FROM rooms WHERE COALESCE(is_active,1)=1 "
            "ORDER BY floor, room_number")
    return [(r["id"], f"F{r['floor']}-{r['room_number']}") for r in rows]


# ---------------------------------------------------------------------------
# Reusable Tab base
# ---------------------------------------------------------------------------
class CRUDTab(ttk.Frame):
    columns: tuple = ()
    form_fields: tuple = ()  # ((field, label, widget_type, options?), ...)

    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.selected_id = None
        self._form_vars = {}
        self._form_widgets = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, columns=self.columns,
                                 show="headings", selectmode="browse")
        for col in self.columns:
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=110, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-3>", self._on_right_click)

        form = ttk.LabelFrame(self, text="Details", padding=8)
        form.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for c in (1, 3):
            form.columnconfigure(c, weight=1)

        for idx, spec in enumerate(self.form_fields):
            field, label, widget_type = spec[0], spec[1], spec[2]
            options = spec[3] if len(spec) > 3 else None
            r, c = divmod(idx, 2)
            ttk.Label(form, text=label + ":").grid(
                row=r, column=c * 2, sticky="w", padx=4, pady=3)
            var = tk.StringVar()
            self._form_vars[field] = var
            if widget_type == "combo":
                w = ttk.Combobox(form, textvariable=var,
                                 values=list(options or []),
                                 state="readonly")
            elif widget_type == "text":
                w = tk.Text(form, height=2, width=30)
            else:
                w = ttk.Entry(form, textvariable=var)
            w.grid(row=r, column=c * 2 + 1, sticky="ew", padx=4, pady=3)
            self._form_widgets[field] = w

        btn_bar = ttk.Frame(self)
        btn_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btn_bar, text="Add",
                   command=self._safe(self._on_save)).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Update Selected",
                   command=self._safe(self._on_update)).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Delete Selected",
                   command=self._safe(self._on_delete)).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Clear Form",
                   command=self._clear_form).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Refresh",
                   command=self._safe(self.refresh)).pack(side="right", padx=2)

    def _safe(self, fn):
        def _wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except sqlite3.IntegrityError as e:
                logger.warning("DB integrity in %s: %s",
                               self.__class__.__name__, e)
                messagebox.showwarning("Validation",
                                       f"Could not save: {e}",
                                       parent=self.app.root)
            except ValueError as e:
                messagebox.showwarning("Invalid input", str(e),
                                       parent=self.app.root)
            except Exception as e:
                logger.exception("Unhandled error in %s",
                                 self.__class__.__name__)
                messagebox.showerror("Error", f"Operation failed: {e}",
                                     parent=self.app.root)
        return _wrapped

    def _form_value(self, field):
        widget = self._form_widgets.get(field)
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c").strip()
        var = self._form_vars.get(field)
        return (var.get().strip() if var else "")

    def _set_form_value(self, field, value):
        widget = self._form_widgets.get(field)
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            if value is not None:
                widget.insert("1.0", str(value))
            return
        var = self._form_vars.get(field)
        if var is not None:
            var.set("" if value is None else str(value))

    def _clear_form(self):
        self.selected_id = None
        for field in self._form_vars:
            self._set_form_value(field, "")

    def _on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        tags = item.get("tags") or [None]
        self.selected_id = tags[0]
        try:
            self.populate_form_from_row(item["values"])
        except Exception:
            logger.exception("populate_form_from_row failed")

    def _on_save(self):
        self.insert_row()
        self.refresh()
        self._clear_form()

    def _on_update(self):
        if not self.selected_id:
            raise ValueError("Select a row to update.")
        self.update_row()
        self.refresh()
        self._clear_form()

    def _on_delete(self):
        if not self.selected_id:
            raise ValueError("Select a row to delete.")
        if not messagebox.askyesno(
                "Confirm",
                "Delete the selected record? This cannot be undone.",
                parent=self.app.root):
            return
        self.delete_row()
        self.refresh()
        self._clear_form()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            for row in self.load_rows():
                row_id = row[0]
                values = row[1:]
                self.tree.insert("", "end", values=values, tags=(row_id,))
        except Exception:
            logger.exception("refresh failed in %s", self.__class__.__name__)

    def load_rows(self):
        raise NotImplementedError

    def insert_row(self):
        raise NotImplementedError

    def update_row(self):
        raise NotImplementedError

    def delete_row(self):
        raise NotImplementedError

    def populate_form_from_row(self, values):
        for field, value in zip(self.columns, values):
            if field in self._form_vars or field in self._form_widgets:
                self._set_form_value(field, value)

    # --- Cross-module right-click menu -------------------------------------
    def _on_right_click(self, event):
        try:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
                self._on_select()
            items = list(self._cross_links() or [])
            if not items:
                return
            menu = tk.Menu(self, tearoff=0)
            for label, action, ctx in items:
                menu.add_command(
                    label=label,
                    command=(lambda a=action, c=ctx:
                            self._dispatch_cross(a, c)))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        except Exception:
            logger.exception("right-click menu failed")

    def _dispatch_cross(self, action, context):
        """Subprocess apps go via IPC; in-process tabs call the parent
        directly. BM is always subprocess so we always use IPC."""
        try:
            from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
                request_open,
            )
            request_open(action, context)
        except Exception:
            logger.exception("cross-dispatch failed: action=%s ctx=%s",
                             action, context)

    def _cross_links(self):
        """Subclasses override to return a list of
        (menu_label, ipc_action, context_dict) tuples for the selected
        row. Return empty / None when no row is selected."""
        return []


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
class BuildingsTab(CRUDTab):
    """Existing ``buildings`` table (PK building_id)."""

    columns = ("building_name", "building_code", "address", "building_type",
               "total_floors", "total_rooms", "is_active")
    form_fields = (
        ("building_name", "Name", "entry"),
        ("building_code", "Code", "entry"),
        ("address", "Address", "entry"),
        ("building_type", "Type", "combo",
         ("academic", "administrative", "residential", "library",
          "sports", "lab", "other")),
        ("year_built", "Year Built", "entry"),
        ("last_renovation_year", "Last Renovated", "entry"),
        ("total_floors", "Total Floors", "entry"),
        ("total_rooms", "Total Rooms", "entry"),
        ("accessibility_features", "Accessibility", "entry"),
        ("is_active", "Active", "combo", ("1", "0")),
    )

    def load_rows(self):
        rows = _fetch_all(
            "SELECT building_id, building_name, building_code, address, "
            "building_type, total_floors, total_rooms, is_active "
            "FROM buildings ORDER BY building_code")
        return [tuple(r) for r in rows]

    def _payload(self):
        name = self._form_value("building_name")
        code = self._form_value("building_code")
        if not name or not code:
            raise ValueError("Name and Code are required.")
        return (
            name, code,
            self._form_value("address"),
            self._form_value("building_type") or "academic",
            int(self._form_value("year_built") or 0) or None,
            int(self._form_value("last_renovation_year") or 0) or None,
            int(self._form_value("total_floors") or 1),
            int(self._form_value("total_rooms") or 0),
            self._form_value("accessibility_features"),
            int(self._form_value("is_active") or 1),
        )

    def insert_row(self):
        _exec(
            "INSERT INTO buildings(building_name, building_code, address, "
            "building_type, year_built, last_renovation_year, total_floors, "
            "total_rooms, accessibility_features, is_active) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE buildings SET building_name=?, building_code=?, "
            "address=?, building_type=?, year_built=?, last_renovation_year=?, "
            "total_floors=?, total_rooms=?, accessibility_features=?, "
            "is_active=? WHERE building_id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM buildings WHERE building_id=?",
              (self.selected_id,))

    def _cross_links(self):
        if not self.selected_id:
            return []
        ctx = {"building_id": int(self.selected_id)}
        return [
            ("Show modules scheduled in this building",
             "module_scheduling", ctx),
            ("Open Timetable filtered to this building",
             "timetable", ctx),
            ("Open Attendance filtered to this building",
             "attendance", ctx),
        ]


class _BuildingPickerMixin:
    """Adds building/room picker widgets bound to the existing schemas."""

    def _refresh_buildings(self):
        opts = buildings_for_picker()
        self._building_map = {label: bid for bid, label in opts}
        combo = self._form_widgets.get("building")
        if isinstance(combo, ttk.Combobox):
            combo.configure(values=list(self._building_map.keys()))

    def _refresh_rooms(self):
        opts = rooms_for_picker()
        self._room_map = {label: rid for rid, label in opts}
        combo = self._form_widgets.get("room")
        if isinstance(combo, ttk.Combobox):
            combo.configure(values=[""] + list(self._room_map.keys()))

    def _refresh_pickers(self):
        self._refresh_buildings()
        self._refresh_rooms()


class RoomsTab(_BuildingPickerMixin, CRUDTab):
    """Existing ``rooms`` table (PK id, FK building_id)."""

    columns = ("building", "room_number", "floor_number", "room_type",
               "capacity", "area_sqft", "status")
    form_fields = (
        ("building", "Building", "combo", []),
        ("room_number", "Room Number", "entry"),
        ("room_name", "Room Name", "entry"),
        ("floor_number", "Floor", "entry"),
        ("room_type", "Type", "combo",
         ("classroom", "lab", "office", "lecture_hall",
          "study_room", "storage", "utility", "other")),
        ("capacity", "Capacity", "entry"),
        ("area_sqft", "Area (sqft)", "entry"),
        ("equipment", "Equipment", "entry"),
        ("status", "Status", "combo",
         ("available", "in_use", "maintenance", "decommissioned")),
        ("accessibility_compliant", "Accessible", "combo", ("1", "0")),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_buildings()

    def refresh(self):
        self._refresh_buildings()
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT r.id, b.building_code || ' — ' || b.building_name, "
            "r.room_number, COALESCE(r.floor_number,0), r.room_type, "
            "r.capacity, r.area_sqft, r.status "
            "FROM rooms r LEFT JOIN buildings b "
            "ON b.building_id = r.building_id "
            "ORDER BY b.building_code, r.floor_number, r.room_number")
        return [tuple(r) for r in rows]

    def _payload(self):
        bid = self._building_map.get(self._form_value("building"))
        if not bid:
            raise ValueError("Pick a building.")
        room_no = self._form_value("room_number")
        if not room_no:
            raise ValueError("Room number is required.")
        return (
            room_no,
            self._form_value("room_name") or None,
            int(self._form_value("floor_number") or 0),
            self._form_value("room_type") or "classroom",
            int(self._form_value("capacity") or 0),
            float(self._form_value("area_sqft") or 0),
            self._form_value("equipment"),
            self._form_value("status") or "available",
            int(self._form_value("accessibility_compliant") or 1),
            bid,
        )

    def insert_row(self):
        _exec(
            "INSERT INTO rooms(room_number, room_name, floor_number, "
            "room_type, capacity, area_sqft, equipment, status, "
            "accessibility_compliant, building_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE rooms SET room_number=?, room_name=?, floor_number=?, "
            "room_type=?, capacity=?, area_sqft=?, equipment=?, status=?, "
            "accessibility_compliant=?, building_id=? WHERE id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM rooms WHERE id=?", (self.selected_id,))

    def _cross_links(self):
        if not self.selected_id:
            return []
        ctx = {"room_id": int(self.selected_id)}
        return [
            ("Show bookings in Module Scheduling",
             "module_scheduling", ctx),
            ("Open Attendance for this room",
             "attendance", ctx),
            ("Open Timetable for this room",
             "timetable", ctx),
            ("Find course/module using this room",
             "course_mgmt", ctx),
        ]


class UtilitiesTab(_BuildingPickerMixin, CRUDTab):
    """Existing ``energy_usage`` table (PK usage_id, FK building_id)."""

    columns = ("building", "usage_type", "reading_date", "meter_reading",
               "consumption", "cost")
    form_fields = (
        ("building", "Building", "combo", []),
        ("usage_type", "Utility", "combo",
         ("electricity", "water", "gas", "heating", "cooling")),
        ("reading_date", "Reading Date", "entry"),
        ("meter_reading", "Meter Reading", "entry"),
        ("consumption", "Consumption", "entry"),
        ("cost", "Cost", "entry"),
        ("billing_period_start", "Period Start", "entry"),
        ("billing_period_end", "Period End", "entry"),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_buildings()

    def refresh(self):
        self._refresh_buildings()
        if not self._form_value("reading_date"):
            self._set_form_value(
                "reading_date", datetime.now().strftime("%Y-%m-%d"))
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT u.usage_id, b.building_code, u.usage_type, "
            "u.reading_date, u.meter_reading, u.consumption, u.cost "
            "FROM energy_usage u "
            "LEFT JOIN buildings b ON b.building_id = u.building_id "
            "ORDER BY u.reading_date DESC LIMIT 500")
        return [tuple(r) for r in rows]

    def _payload(self):
        bid = self._building_map.get(self._form_value("building"))
        if not bid:
            raise ValueError("Pick a building.")
        return (
            bid,
            self._form_value("usage_type") or "electricity",
            self._form_value("reading_date") or datetime.now().strftime("%Y-%m-%d"),
            float(self._form_value("meter_reading") or 0),
            float(self._form_value("consumption") or 0),
            float(self._form_value("cost") or 0),
            self._form_value("billing_period_start") or None,
            self._form_value("billing_period_end") or None,
        )

    def insert_row(self):
        _exec(
            "INSERT INTO energy_usage(building_id, usage_type, reading_date, "
            "meter_reading, consumption, cost, billing_period_start, "
            "billing_period_end) VALUES (?,?,?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE energy_usage SET building_id=?, usage_type=?, "
            "reading_date=?, meter_reading=?, consumption=?, cost=?, "
            "billing_period_start=?, billing_period_end=? WHERE usage_id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM energy_usage WHERE usage_id=?",
              (self.selected_id,))


class CleaningTab(_BuildingPickerMixin, CRUDTab):
    """New ``bm_cleaning_schedules`` (no existing equivalent)."""

    columns = ("building", "room", "frequency", "last_cleaned",
               "next_due", "assigned_to", "status")
    form_fields = (
        ("building", "Building", "combo", []),
        ("room", "Room (optional)", "combo", []),
        ("frequency", "Frequency", "combo",
         ("daily", "weekly", "fortnightly", "monthly", "quarterly")),
        ("last_cleaned", "Last Cleaned", "entry"),
        ("next_due", "Next Due", "entry"),
        ("assigned_to", "Assigned To", "entry"),
        ("status", "Status", "combo",
         ("scheduled", "in_progress", "complete", "overdue")),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_pickers()

    def refresh(self):
        self._refresh_pickers()
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT c.id, b.building_code, "
            "COALESCE('F'||COALESCE(r.floor_number,0)||'-'||r.room_number,"
            "         '(building-wide)'), "
            "c.frequency, c.last_cleaned, c.next_due, c.assigned_to, c.status "
            "FROM bm_cleaning_schedules c "
            "LEFT JOIN buildings b ON b.building_id = c.building_id "
            "LEFT JOIN rooms r ON r.id = c.room_id "
            "ORDER BY c.next_due IS NULL, c.next_due")
        return [tuple(r) for r in rows]

    def _payload(self):
        bid = self._building_map.get(self._form_value("building"))
        if not bid:
            raise ValueError("Pick a building.")
        room_label = self._form_value("room")
        rid = self._room_map.get(room_label) if room_label else None
        return (
            bid, rid,
            self._form_value("frequency") or "weekly",
            self._form_value("last_cleaned") or None,
            self._form_value("next_due") or None,
            self._form_value("assigned_to"),
            self._form_value("status") or "scheduled",
        )

    def insert_row(self):
        _exec(
            "INSERT INTO bm_cleaning_schedules(building_id, room_id, "
            "frequency, last_cleaned, next_due, assigned_to, status) "
            "VALUES (?,?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE bm_cleaning_schedules SET building_id=?, room_id=?, "
            "frequency=?, last_cleaned=?, next_due=?, assigned_to=?, "
            "status=? WHERE id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM bm_cleaning_schedules WHERE id=?",
              (self.selected_id,))


class MaintenanceTab(_BuildingPickerMixin, CRUDTab):
    """Existing ``maintenance_requests`` table (PK request_id)."""

    columns = ("building", "room", "request_type", "priority", "status",
               "reported_by", "assigned_to", "reported_date")
    form_fields = (
        ("building", "Building", "combo", []),
        ("room", "Room (optional)", "combo", []),
        ("request_type", "Type", "combo",
         ("electrical", "plumbing", "hvac", "carpentry", "painting",
          "cleaning", "pest_control", "structural", "other")),
        ("priority", "Priority", "combo",
         ("low", "medium", "high", "urgent")),
        ("status", "Status", "combo",
         ("open", "in_progress", "blocked", "resolved", "closed")),
        ("reported_by", "Reported By", "entry"),
        ("assigned_to", "Assigned To", "entry"),
        ("scheduled_date", "Scheduled", "entry"),
        ("cost", "Cost", "entry"),
        ("description", "Description", "text"),
        ("notes", "Notes", "text"),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_pickers()

    def refresh(self):
        self._refresh_pickers()
        if not self._form_value("reported_by"):
            self._set_form_value(
                "reported_by", _user_display_name(self.app.user))
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT m.request_id, b.building_code, "
            "COALESCE('F'||COALESCE(r.floor_number,0)||'-'||r.room_number,''), "
            "m.request_type, m.priority, m.status, m.reported_by, "
            "m.assigned_to, m.reported_date "
            "FROM maintenance_requests m "
            "LEFT JOIN buildings b ON b.building_id = m.building_id "
            "LEFT JOIN rooms r ON r.id = m.room_id "
            "ORDER BY CASE m.priority "
            " WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            " WHEN 'medium' THEN 2 ELSE 3 END, m.reported_date DESC")
        return [tuple(r) for r in rows]

    def _payload(self, *, for_insert):
        bid = self._building_map.get(self._form_value("building"))
        if not bid:
            raise ValueError("Pick a building.")
        room_label = self._form_value("room")
        rid = self._room_map.get(room_label) if room_label else None
        if not self._form_value("request_type"):
            raise ValueError("Request type is required.")
        status = self._form_value("status") or "open"
        completion = (datetime.now().strftime("%Y-%m-%d")
                      if status in ("resolved", "closed") else None)
        location_type = "room" if rid else "building"
        cost_raw = self._form_value("cost")
        cost = float(cost_raw) if cost_raw else None
        common = (
            location_type, bid, rid,
            self._form_value("request_type"),
            self._form_value("priority") or "medium",
            self._form_value("description"),
            self._form_value("reported_by"),
            self._form_value("assigned_to"),
            self._form_value("scheduled_date") or None,
            completion, status, cost,
            self._form_value("notes"),
        )
        if for_insert:
            return (*common, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return common

    def insert_row(self):
        payload = self._payload(for_insert=True)
        _exec(
            "INSERT INTO maintenance_requests(location_type, building_id, "
            "room_id, request_type, priority, description, reported_by, "
            "assigned_to, scheduled_date, completion_date, status, cost, "
            "notes, reported_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", payload)

    def update_row(self):
        payload = self._payload(for_insert=False)
        _exec(
            "UPDATE maintenance_requests SET location_type=?, building_id=?, "
            "room_id=?, request_type=?, priority=?, description=?, "
            "reported_by=?, assigned_to=?, scheduled_date=?, "
            "completion_date=?, status=?, cost=?, notes=? WHERE request_id=?",
            (*payload, self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM maintenance_requests WHERE request_id=?",
              (self.selected_id,))

    def _cross_links(self):
        if not self.selected_id:
            return []
        # Look up the room_id for the selected request so the receiver
        # can filter by room rather than the maintenance request itself.
        rows = _fetch_all(
            "SELECT room_id, building_id FROM maintenance_requests "
            "WHERE request_id=?", (self.selected_id,))
        if not rows:
            return []
        room_id = rows[0]["room_id"]
        building_id = rows[0]["building_id"]
        ctx = {}
        if room_id:
            ctx["room_id"] = int(room_id)
        if building_id:
            ctx["building_id"] = int(building_id)
        if not ctx:
            return []
        items = [
            ("Show this room/building in Scheduling",
             "module_scheduling", ctx),
        ]
        if room_id:
            items.append(
                ("Open Attendance for this room", "attendance",
                 {"room_id": int(room_id)}))
        return items


class OccupancyTab(_BuildingPickerMixin, CRUDTab):
    """New ``bm_occupancy_records`` (no existing equivalent)."""

    columns = ("building", "room", "timestamp", "occupant_count",
               "capacity", "utilization_pct")
    form_fields = (
        ("building", "Building", "combo", []),
        ("room", "Room (optional)", "combo", []),
        ("timestamp", "Timestamp", "entry"),
        ("occupant_count", "Occupants", "entry"),
        ("capacity", "Capacity", "entry"),
    )

    def __init__(self, master, app):
        self._analytics_label = None
        super().__init__(master, app)
        self._refresh_pickers()
        self._build_analytics()
        self._update_analytics()

    def _build_analytics(self):
        panel = ttk.LabelFrame(self, text="Utilisation Summary", padding=8)
        panel.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._analytics_label = ttk.Label(
            panel, text="—", justify="left", font=("Arial", 10))
        self._analytics_label.pack(anchor="w")

    def refresh(self):
        self._refresh_pickers()
        if not self._form_value("timestamp"):
            self._set_form_value(
                "timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
        super().refresh()
        self._update_analytics()

    def _update_analytics(self):
        if self._analytics_label is None:
            return
        try:
            rows = _fetch_all(
                "SELECT b.building_code, AVG(o.utilization_pct), "
                "MAX(o.utilization_pct), COUNT(*) "
                "FROM bm_occupancy_records o "
                "LEFT JOIN buildings b ON b.building_id=o.building_id "
                "GROUP BY b.building_code "
                "ORDER BY AVG(o.utilization_pct) DESC")
            if not rows:
                self._analytics_label.config(text="No occupancy data yet.")
                return
            lines = ["{:<10} avg={:>5.1f}%  peak={:>5.1f}%  n={}".format(
                r[0] or "?", r[1] or 0, r[2] or 0, r[3]) for r in rows]
            self._analytics_label.config(text="\n".join(lines))
        except Exception:
            logger.exception("occupancy analytics failed")

    def load_rows(self):
        rows = _fetch_all(
            "SELECT o.id, b.building_code, "
            "COALESCE('F'||COALESCE(r.floor_number,0)||'-'||r.room_number,"
            "         '(building-wide)'), "
            "o.timestamp, o.occupant_count, o.capacity, o.utilization_pct "
            "FROM bm_occupancy_records o "
            "LEFT JOIN buildings b ON b.building_id = o.building_id "
            "LEFT JOIN rooms r ON r.id = o.room_id "
            "ORDER BY o.timestamp DESC LIMIT 500")
        return [tuple(r) for r in rows]

    def _payload(self):
        bid = self._building_map.get(self._form_value("building"))
        if not bid:
            raise ValueError("Pick a building.")
        room_label = self._form_value("room")
        rid = self._room_map.get(room_label) if room_label else None
        ts = self._form_value("timestamp") or datetime.now().isoformat()
        occ = int(self._form_value("occupant_count") or 0)
        cap = int(self._form_value("capacity") or 0)
        if cap < 0 or occ < 0:
            raise ValueError("Counts must be non-negative.")
        util = (occ / cap * 100.0) if cap > 0 else 0.0
        return (bid, rid, ts, occ, cap, util)

    def insert_row(self):
        _exec(
            "INSERT INTO bm_occupancy_records(building_id, room_id, "
            "timestamp, occupant_count, capacity, utilization_pct) "
            "VALUES (?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE bm_occupancy_records SET building_id=?, room_id=?, "
            "timestamp=?, occupant_count=?, capacity=?, utilization_pct=? "
            "WHERE id=?", (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM bm_occupancy_records WHERE id=?",
              (self.selected_id,))


class AccessCardsTab(CRUDTab):
    """Existing ``access_cards`` table (PK card_id).

    ``buildings_access`` is stored as a comma-separated list of building
    codes; pick one from the dropdown to append, or edit by hand.
    """

    columns = ("card_number", "user_name", "card_type", "access_level",
               "buildings_access", "status", "expiry_date")
    form_fields = (
        ("card_number", "Card Number", "entry"),
        ("user_id", "User ID", "entry"),
        ("user_name", "User Name", "entry"),
        ("card_type", "Card Type", "combo",
         ("staff", "student", "contractor", "visitor", "service")),
        ("access_level", "Access Level", "combo",
         ("standard", "elevated", "restricted", "high_security")),
        ("buildings_access", "Buildings (csv codes)", "entry"),
        ("issue_date", "Issue Date", "entry"),
        ("expiry_date", "Expiry Date", "entry"),
        ("status", "Status", "combo",
         ("active", "suspended", "lost", "expired", "revoked")),
        ("issued_by", "Issued By", "entry"),
        ("notes", "Notes", "text"),
    )

    def refresh(self):
        if not self._form_value("issued_by"):
            self._set_form_value(
                "issued_by", _user_display_name(self.app.user))
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT card_id, card_number, user_name, card_type, "
            "access_level, buildings_access, status, expiry_date "
            "FROM access_cards ORDER BY status, expiry_date")
        return [tuple(r) for r in rows]

    def _payload(self):
        cn = self._form_value("card_number")
        if not cn:
            raise ValueError("Card number is required.")
        return (
            cn,
            self._form_value("user_id"),
            self._form_value("user_name"),
            self._form_value("card_type") or "staff",
            self._form_value("access_level") or "standard",
            self._form_value("buildings_access"),
            self._form_value("issue_date") or datetime.now().strftime("%Y-%m-%d"),
            self._form_value("expiry_date") or None,
            self._form_value("status") or "active",
            self._form_value("issued_by"),
            self._form_value("notes"),
        )

    def insert_row(self):
        _exec(
            "INSERT INTO access_cards(card_number, user_id, user_name, "
            "card_type, access_level, buildings_access, issue_date, "
            "expiry_date, status, issued_by, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (*self._payload(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def update_row(self):
        _exec(
            "UPDATE access_cards SET card_number=?, user_id=?, user_name=?, "
            "card_type=?, access_level=?, buildings_access=?, issue_date=?, "
            "expiry_date=?, status=?, issued_by=?, notes=? WHERE card_id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM access_cards WHERE card_id=?",
              (self.selected_id,))


class InspectionsTab(_BuildingPickerMixin, CRUDTab):
    """Existing ``housing_inspections`` table.

    ``inspection_id`` is TEXT; auto-generated as ``INS-YYYYMMDDHHMMSS-<n>``.
    ``room_id`` is TEXT; we store the rooms.id as text. For
    building-level inspections (lift, fire-safety), pick any
    representative room in the building.
    """

    columns = ("room", "inspection_type", "inspector", "inspection_date",
               "status", "follow_up_date")
    form_fields = (
        ("building", "Building (filter)", "combo", []),
        ("room", "Room", "combo", []),
        ("inspection_type", "Type", "combo",
         ("lift", "fire_safety", "electrical", "gas", "asbestos",
          "legionella", "structural", "general", "housing")),
        ("inspector", "Inspector", "entry"),
        ("inspection_date", "Inspection Date", "entry"),
        ("status", "Status", "combo",
         ("scheduled", "in_progress", "passed", "failed",
          "remedial_required")),
        ("follow_up_date", "Follow-up Date", "entry"),
        ("findings", "Findings", "text"),
        ("action_required", "Action Required", "text"),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_pickers()

    def refresh(self):
        self._refresh_pickers()
        if not self._form_value("inspection_date"):
            self._set_form_value(
                "inspection_date", datetime.now().strftime("%Y-%m-%d"))
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT i.inspection_id, "
            "COALESCE('F'||COALESCE(r.floor_number,0)||'-'||r.room_number, "
            "         i.room_id), "
            "i.inspection_type, i.inspector, i.inspection_date, i.status, "
            "i.follow_up_date "
            "FROM housing_inspections i "
            "LEFT JOIN rooms r ON CAST(r.id AS TEXT) = i.room_id "
            "ORDER BY i.inspection_date DESC LIMIT 500")
        return [tuple(r) for r in rows]

    def _gen_inspection_id(self):
        # INS-YYYYMMDDHHMMSS-<random4>
        import random
        return "INS-{}-{:04d}".format(
            datetime.now().strftime("%Y%m%d%H%M%S"),
            random.randint(0, 9999))

    def _payload(self):
        room_label = self._form_value("room")
        rid = self._room_map.get(room_label) if room_label else None
        if not rid:
            raise ValueError(
                "Pick a room (use any room in the building for "
                "building-wide inspections like lift / fire-safety).")
        if not self._form_value("inspection_type"):
            raise ValueError("Inspection type is required.")
        return (
            str(rid),
            self._form_value("inspector"),
            self._form_value("inspection_date") or datetime.now().strftime("%Y-%m-%d"),
            self._form_value("inspection_type"),
            self._form_value("status") or "scheduled",
            self._form_value("findings"),
            self._form_value("action_required"),
            self._form_value("follow_up_date") or None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def insert_row(self):
        _exec(
            "INSERT INTO housing_inspections(inspection_id, room_id, "
            "inspector, inspection_date, inspection_type, status, findings, "
            "action_required, follow_up_date, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (self._gen_inspection_id(), *self._payload()))

    def update_row(self):
        # _payload returns 9 cols (excluding inspection_id); strip the
        # trailing created_at since we want to set updated_at instead.
        payload = self._payload()
        updated_at = payload[-1]
        body = payload[:-1]
        _exec(
            "UPDATE housing_inspections SET room_id=?, inspector=?, "
            "inspection_date=?, inspection_type=?, status=?, findings=?, "
            "action_required=?, follow_up_date=?, updated_at=? "
            "WHERE inspection_id=?",
            (*body, updated_at, self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM housing_inspections WHERE inspection_id=?",
              (self.selected_id,))

    def _cross_links(self):
        if not self.selected_id:
            return []
        rows = _fetch_all(
            "SELECT room_id FROM housing_inspections WHERE inspection_id=?",
            (self.selected_id,))
        if not rows or not rows[0]["room_id"]:
            return []
        try:
            rid = int(rows[0]["room_id"])
        except (TypeError, ValueError):
            return []
        ctx = {"room_id": rid}
        return [
            ("Open Module Scheduling for this room",
             "module_scheduling", ctx),
            ("Open Attendance for this room", "attendance", ctx),
            ("Open Timetable for this room", "timetable", ctx),
        ]


# ---------------------------------------------------------------------------
# Bookings tab — embeds the room_booking _Frame so book/find/cancel lives
# inside the unified Facilities window instead of needing its own launcher.
# ---------------------------------------------------------------------------
class BookingsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=4)
        self.app = app
        # Lazy import to avoid circular: room_booking_app sits alongside us.
        from education_system.university_system.modules.domain.campus.facilities.gui.room_booking_app import (
            _Frame as _BookingFrame,
        )
        _BookingFrame(self, user=app.user).pack(fill="both", expand=True)


# ---------------------------------------------------------------------------
# Work Orders — drawn from the ``work_orders`` table created by the
# facilities_management_core service layer.
# ---------------------------------------------------------------------------
class WorkOrdersTab(CRUDTab):
    """``work_orders`` table — derived from maintenance requests."""

    columns = ("request_id", "work_order_type", "assigned_technician",
               "status", "estimated_hours", "actual_hours", "total_cost")
    form_fields = (
        ("request_id", "Linked Request ID", "entry"),
        ("work_order_type", "Type", "combo",
         ("repair", "install", "inspect", "replace", "preventive", "emergency")),
        ("description", "Description", "text"),
        ("assigned_technician", "Technician", "entry"),
        ("estimated_hours", "Est. Hours", "entry"),
        ("actual_hours", "Actual Hours", "entry"),
        ("materials_cost", "Materials £", "entry"),
        ("labor_cost", "Labour £", "entry"),
        ("start_date", "Start Date", "entry"),
        ("completion_date", "Completion Date", "entry"),
        ("status", "Status", "combo",
         ("open", "in_progress", "blocked", "completed", "cancelled")),
    )

    def load_rows(self):
        rows = _fetch_all(
            "SELECT work_order_id, request_id, work_order_type, "
            "assigned_technician, status, estimated_hours, actual_hours, "
            "total_cost FROM work_orders ORDER BY "
            "CASE status WHEN 'in_progress' THEN 0 WHEN 'open' THEN 1 "
            "ELSE 2 END, work_order_id DESC")
        return [tuple(r) for r in rows]

    def _payload(self):
        req = self._form_value("request_id")
        if not req:
            raise ValueError("Linked Request ID is required.")
        materials = float(self._form_value("materials_cost") or 0)
        labour = float(self._form_value("labor_cost") or 0)
        return (
            int(req),
            self._form_value("work_order_type") or "repair",
            self._form_value("description"),
            self._form_value("assigned_technician"),
            float(self._form_value("estimated_hours") or 0) or None,
            float(self._form_value("actual_hours") or 0) or None,
            materials, labour,
            (materials + labour) if (materials or labour) else None,
            self._form_value("start_date") or None,
            self._form_value("completion_date") or None,
            self._form_value("status") or "open",
        )

    def insert_row(self):
        _exec(
            "INSERT INTO work_orders(request_id, work_order_type, description, "
            "assigned_technician, estimated_hours, actual_hours, materials_cost, "
            "labor_cost, total_cost, start_date, completion_date, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", self._payload())

    def update_row(self):
        _exec(
            "UPDATE work_orders SET request_id=?, work_order_type=?, "
            "description=?, assigned_technician=?, estimated_hours=?, "
            "actual_hours=?, materials_cost=?, labor_cost=?, total_cost=?, "
            "start_date=?, completion_date=?, status=? WHERE work_order_id=?",
            (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM work_orders WHERE work_order_id=?",
              (self.selected_id,))


# ---------------------------------------------------------------------------
# Asset Inventory — ``facility_assets`` table.
# ---------------------------------------------------------------------------
class AssetsTab(_BuildingPickerMixin, CRUDTab):
    """``facility_assets`` table."""

    columns = ("asset_tag", "asset_name", "asset_type", "building", "room",
               "condition", "status", "warranty_expiry")
    form_fields = (
        ("asset_tag", "Asset Tag", "entry"),
        ("asset_name", "Name", "entry"),
        ("asset_type", "Type", "combo",
         ("furniture", "equipment", "electronics", "appliance",
          "av_equipment", "lab_equipment", "vehicle", "other")),
        ("building", "Building", "combo", []),
        ("room", "Room (optional)", "combo", []),
        ("purchase_date", "Purchase Date", "entry"),
        ("purchase_cost", "Purchase £", "entry"),
        ("warranty_expiry", "Warranty Expiry", "entry"),
        ("maintenance_schedule", "Maintenance Schedule", "entry"),
        ("last_maintenance_date", "Last Serviced", "entry"),
        ("condition", "Condition", "combo",
         ("excellent", "good", "fair", "poor", "broken")),
        ("status", "Status", "combo",
         ("active", "in_storage", "loaned", "retired", "lost")),
    )

    def __init__(self, master, app):
        super().__init__(master, app)
        self._refresh_pickers()

    def refresh(self):
        self._refresh_pickers()
        super().refresh()

    def load_rows(self):
        rows = _fetch_all(
            "SELECT a.asset_id, a.asset_tag, a.asset_name, a.asset_type, "
            "b.building_code, "
            "COALESCE('F'||COALESCE(r.floor_number,0)||'-'||r.room_number,''), "
            "a.condition, a.status, a.warranty_expiry "
            "FROM facility_assets a "
            "LEFT JOIN buildings b ON b.building_id = a.building_id "
            "LEFT JOIN rooms r ON r.id = a.room_id "
            "ORDER BY a.asset_tag")
        return [tuple(r) for r in rows]

    def _payload(self):
        tag = self._form_value("asset_tag")
        name = self._form_value("asset_name")
        if not tag or not name:
            raise ValueError("Asset tag and name are required.")
        bid = self._building_map.get(self._form_value("building"))
        room_label = self._form_value("room")
        rid = self._room_map.get(room_label) if room_label else None
        return (
            name,
            self._form_value("asset_type") or "equipment",
            tag, bid, rid,
            self._form_value("purchase_date") or None,
            float(self._form_value("purchase_cost") or 0),
            self._form_value("warranty_expiry") or None,
            self._form_value("maintenance_schedule"),
            self._form_value("last_maintenance_date") or None,
            self._form_value("condition") or "good",
            self._form_value("status") or "active",
        )

    def insert_row(self):
        _exec(
            "INSERT INTO facility_assets(asset_name, asset_type, asset_tag, "
            "building_id, room_id, purchase_date, purchase_cost, "
            "warranty_expiry, maintenance_schedule, last_maintenance_date, "
            "condition, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            self._payload())

    def update_row(self):
        _exec(
            "UPDATE facility_assets SET asset_name=?, asset_type=?, "
            "asset_tag=?, building_id=?, room_id=?, purchase_date=?, "
            "purchase_cost=?, warranty_expiry=?, maintenance_schedule=?, "
            "last_maintenance_date=?, condition=?, status=? "
            "WHERE asset_id=?", (*self._payload(), self.selected_id))

    def delete_row(self):
        _exec("DELETE FROM facility_assets WHERE asset_id=?",
              (self.selected_id,))


# ---------------------------------------------------------------------------
# Reports & Analytics — read-only summary dashboard pulling from the same
# tables. Refreshable; no CRUD form.
# ---------------------------------------------------------------------------
class ReportsTab(ttk.Frame):
    """Read-only summary view across buildings / rooms / bookings /
    maintenance / occupancy / energy."""

    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(top, text="Refresh",
                   command=self.refresh).pack(side="right")
        ttk.Label(top, text="Facilities Reports & Analytics",
                  font=("Arial", 12, "bold")).pack(side="left")

        self.text = tk.Text(self, wrap="word", font=("Courier", 10))
        self.text.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.text.configure(yscrollcommand=sb.set)
        self.refresh()

    def _section(self, title):
        self.text.insert("end", f"\n{title}\n{'=' * len(title)}\n")

    def refresh(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        # Buildings + rooms
        bcount = _fetch_all("SELECT COUNT(*) AS n FROM buildings "
                            "WHERE COALESCE(is_active,1)=1")
        rcount = _fetch_all("SELECT COUNT(*) AS n FROM rooms "
                            "WHERE COALESCE(is_active,1)=1")
        self._section("Estate")
        self.text.insert("end", f"  Active buildings: {bcount[0]['n'] if bcount else 0}\n")
        self.text.insert("end", f"  Active rooms:     {rcount[0]['n'] if rcount else 0}\n")

        # Maintenance state
        self._section("Maintenance — open requests by priority")
        rows = _fetch_all(
            "SELECT priority, COUNT(*) AS n FROM maintenance_requests "
            "WHERE status NOT IN ('resolved','closed','cancelled') "
            "GROUP BY priority "
            "ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END")
        if rows:
            for r in rows:
                self.text.insert("end",
                                 f"  {(r['priority'] or 'unspecified'):<10} {r['n']}\n")
        else:
            self.text.insert("end", "  (no open requests)\n")

        # Work orders by status
        self._section("Work Orders by status")
        rows = _fetch_all("SELECT status, COUNT(*) AS n FROM work_orders "
                          "GROUP BY status")
        if rows:
            for r in rows:
                self.text.insert("end",
                                 f"  {(r['status'] or '?'):<14} {r['n']}\n")
        else:
            self.text.insert("end", "  (no work orders recorded)\n")

        # Bookings — upcoming
        self._section("Upcoming room bookings (next 30)")
        rows = _fetch_all(
            "SELECT booking_id, room_id, start_datetime, booked_by, purpose "
            "FROM room_bookings "
            "WHERE COALESCE(booking_status, 'confirmed') = 'confirmed' "
            "AND start_datetime >= ? ORDER BY start_datetime LIMIT 30",
            (datetime.now().strftime("%Y-%m-%d %H:%M"),))
        if rows:
            for r in rows:
                self.text.insert("end",
                                 f"  #{r['booking_id']:<5} room={r['room_id']:<5}  "
                                 f"{r['start_datetime']}  {r['booked_by'] or '—'}  "
                                 f"{(r['purpose'] or '')[:40]}\n")
        else:
            self.text.insert("end", "  (none)\n")

        # Occupancy summary — reuses OccupancyManager
        self._section("Occupancy — avg / peak per building")
        try:
            from education_system.university_system.modules.domain.campus.facilities.services import (
                OccupancyManager,
            )
            for row in OccupancyManager.utilisation_summary():
                self.text.insert("end",
                                 f"  {(row['building_code'] or '?'):<10} "
                                 f"avg={(row['avg_pct'] or 0):>5.1f}%   "
                                 f"peak={(row['peak_pct'] or 0):>5.1f}%   "
                                 f"n={row['sample_count']}\n")
        except Exception as exc:
            self.text.insert("end", f"  (unavailable: {exc})\n")

        # Energy — most recent reading per building
        self._section("Energy — last 10 readings")
        rows = _fetch_all(
            "SELECT b.building_code, u.usage_type, u.reading_date, "
            "u.consumption, u.cost "
            "FROM energy_usage u "
            "LEFT JOIN buildings b ON b.building_id = u.building_id "
            "ORDER BY u.reading_date DESC LIMIT 10")
        if rows:
            for r in rows:
                self.text.insert("end",
                                 f"  {(r['building_code'] or '?'):<10} "
                                 f"{(r['usage_type'] or '?'):<12} {r['reading_date']}  "
                                 f"consumption={r['consumption']:<8.2f}  £{r['cost']:.2f}\n")
        else:
            self.text.insert("end", "  (no readings)\n")

        self.text.configure(state="disabled")


# ---------------------------------------------------------------------------
# App shell
# ---------------------------------------------------------------------------
class BuildingManagementApp:
    """Unified Facilities application.

    Originally the Building Management standalone Tk app. Now also hosts what
    were the separate Room Booking and Facilities-management GUIs as tabs, so
    there is a single window covering buildings, rooms, bookings, utilities,
    cleaning, maintenance, work orders, occupancy, access cards, inspections,
    assets, and reports. ``FacilitiesApp`` is an alias.
    """

    def __init__(self, parent=None):
        """`parent` may be a Tk root/Toplevel to host the app, or None to
        run standalone (creates its own Tk root). Lets the unified main GUI
        embed this without a subprocess."""
        self.user = _get_current_user()
        init_db()
        self._owns_root = parent is None
        if self._owns_root:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel(parent)
        self.root.title("Facilities Management")
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self._build_header()
        self._build_notebook()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        header = tk.Frame(self.root, bg="#2c3e50", height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏢 Facilities Management",
                 font=("Arial", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=12)
        tk.Label(header,
                 text=f"Signed in: {_user_display_name(self.user)}",
                 bg="#2c3e50", fg="#dfe6ec",
                 font=("Arial", 10)).pack(side="right", padx=12)

    def _build_notebook(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tabs = {
            "Buildings": BuildingsTab(nb, self),
            "Rooms": RoomsTab(nb, self),
            "Bookings": BookingsTab(nb, self),
            "Utilities": UtilitiesTab(nb, self),
            "Cleaning": CleaningTab(nb, self),
            "Maintenance": MaintenanceTab(nb, self),
            "Work Orders": WorkOrdersTab(nb, self),
            "Occupancy": OccupancyTab(nb, self),
            "Access Cards": AccessCardsTab(nb, self),
            "Inspections": InspectionsTab(nb, self),
            "Assets": AssetsTab(nb, self),
            "Reports": ReportsTab(nb, self),
        }
        for label, frame in self.tabs.items():
            nb.add(frame, text=label)
        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, _evt=None):
        try:
            for tab in self.tabs.values():
                if hasattr(tab, "_refresh_buildings"):
                    tab._refresh_buildings()
                if hasattr(tab, "_refresh_pickers"):
                    tab._refresh_pickers()
        except Exception:
            logger.exception("tab change refresh failed")

    def _on_close(self):
        try:
            self.root.destroy()
        except Exception:
            logger.exception("close failed")

    def run(self):
        logger.info("Facilities Management starting (db=%s, user=%s)",
                    DB_PATH, _user_display_name(self.user))
        if self._owns_root:
            self.root.mainloop()


# Public alias — the consolidated app is the Facilities app.
FacilitiesApp = BuildingManagementApp


def launch_in_window(parent, auth=None):
    """Open the unified Facilities app in a Toplevel under `parent`.

    Returns the BuildingManagementApp instance. Used by
    facilities_management_core.launch_facilities_management_gui so the
    existing 'Facilities' button now lands here.
    """
    app = BuildingManagementApp(parent=parent)
    return app


def main():
    try:
        BuildingManagementApp().run()
    except Exception:
        logger.exception("Facilities Management failed to start")
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Facilities Management",
                "Failed to start. See logs for details.")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
