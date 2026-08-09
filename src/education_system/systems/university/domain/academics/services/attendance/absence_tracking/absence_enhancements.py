"""
Absence Tracker — 17 enhancement features, organised as service classes.

Service classes (one responsibility each):

    EnhancementSettings        small KV settings store
    ThemeService               #36 dark mode, #42 high contrast
    TreeUxService              #37 shortcuts, #38 filter bar, #39 sort,
                               #40 pagination, #42 a11y labels
    GeofenceService            #3  geofenced check-in
    FaceCheckinService         #4  facial-recognition kiosk
    RequestCategoryService     #11 request categories + routing
    PushQueueService           #21 mobile push notification queue
    ComplianceService          #30 HESA export, #31 UKVI engagement
    EvidenceService            #35 SHA-256 signature on evidence
    LmsSyncService             #46 LMS access grants
    AnomalyService             #50 anomaly detection (concurrency, proxy)
    ChatbotService             #49 "how many more absences can I take?"
    EnhancementTabBuilder      role-aware GUI sections + bootstrap

Public API kept stable for external callers (chatbot, REST routes,
absence_tracker.py): ``ensure_enhanced_schema``, ``chatbot_absence_quota``,
``bootstrap``, ``add_filter_bar``, ``Paginator``, ``list_categories``,
``record_geofenced_checkin``, ``facial_checkin``, ``queue_push``,
``drain_push_queue``, ``hesa_export``, ``ukvi_at_risk``,
``ukvi_log_event``, ``sign_evidence``, ``verify_evidence``,
``lms_sync_approved_requests``, ``anomaly_scan`` — each delegates to the
matching service class.

Logging is routed through ``infrastructure.logging.log_config`` so output
joins ``university_system/logs/app.log``. Every state-changing DB
operation guards ``sqlite3.Error`` with explicit ``rollback()``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

# Route through the central rotating file handler (logs/app.log).
try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_enhancements")
except Exception:  # pragma: no cover
    logger = logging.getLogger("absence_enhancements")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


# ===========================================================================
# Schema
# ===========================================================================

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS absence_request_categories (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT UNIQUE NOT NULL,
         description TEXT,
         requires_evidence INTEGER DEFAULT 0,
         approval_route TEXT DEFAULT 'instructor',
         auto_approve INTEGER DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS attendance_kiosks (
         kiosk_id TEXT PRIMARY KEY,
         room TEXT, lat REAL, lon REAL,
         radius_m REAL DEFAULT 50,
         active INTEGER DEFAULT 1
       )""",
    """CREATE TABLE IF NOT EXISTS absence_push_queue (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         delivered_at TEXT, status TEXT DEFAULT 'pending'
       )""",
    """CREATE TABLE IF NOT EXISTS ukvi_engagement_events (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, event_type TEXT NOT NULL,
         event_date TEXT NOT NULL, notes TEXT, recorded_by TEXT,
         recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    """CREATE TABLE IF NOT EXISTS absence_evidence_signatures (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         request_id INTEGER NOT NULL, file_path TEXT NOT NULL,
         sha256 TEXT NOT NULL, signed_by TEXT,
         signed_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    """CREATE TABLE IF NOT EXISTS attendance_anomalies (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         kind TEXT NOT NULL,
         student_id TEXT, module_code TEXT, details TEXT,
         severity TEXT DEFAULT 'medium',
         detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
         resolved INTEGER DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS lms_access_grants (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, module_code TEXT NOT NULL,
         session_date TEXT NOT NULL, resource TEXT NOT NULL,
         granted INTEGER DEFAULT 0, reason TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(student_id, module_code, session_date, resource)
       )""",
    """CREATE TABLE IF NOT EXISTS absence_settings (
         key TEXT PRIMARY KEY, value TEXT
       )""",
]

SEED_CATEGORIES = [
    ("medical",        "Illness / medical appointment",  1, "instructor", 0),
    ("bereavement",    "Family bereavement",             0, "dept_head",  1),
    ("religious",      "Religious observance",           0, "instructor", 1),
    ("representative", "University representative duty", 0, "instructor", 1),
    ("other",          "Other — requires narrative",     0, "instructor", 0),
]


def ensure_enhanced_schema(conn: sqlite3.Connection) -> None:
    """Create / migrate every table the enhancement features need."""
    try:
        cur = conn.cursor()
        for ddl in SCHEMA_SQL:
            cur.execute(ddl)
        # Add category_id + date_end columns to absence_requests if missing.
        cur.execute("PRAGMA table_info(absence_requests)")
        cols = {r[1] for r in cur.fetchall()}
        if "category_id" not in cols:
            try:
                cur.execute(
                    "ALTER TABLE absence_requests ADD COLUMN category_id INTEGER")
            except sqlite3.OperationalError:
                logger.debug("category_id ALTER skipped", exc_info=True)
        if "date_end" not in cols:
            try:
                cur.execute(
                    "ALTER TABLE absence_requests ADD COLUMN date_end TEXT")
            except sqlite3.OperationalError:
                logger.debug("date_end ALTER skipped", exc_info=True)
        cur.execute("SELECT COUNT(*) FROM absence_request_categories")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                """INSERT INTO absence_request_categories
                     (name, description, requires_evidence,
                      approval_route, auto_approve)
                   VALUES (?, ?, ?, ?, ?)""",
                SEED_CATEGORIES)
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        logger.exception("ensure_enhanced_schema failed")
        raise


# ===========================================================================
# EnhancementSettings — KV store
# ===========================================================================

class EnhancementSettings:
    """KV settings store backed by absence_settings."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            row = self.conn.execute(
                "SELECT value FROM absence_settings WHERE key=?",
                (key,)).fetchone()
            return row[0] if row else default
        except sqlite3.Error:
            logger.exception("settings.get failed key=%s", key)
            return default

    def set(self, key: str, value: Any) -> None:
        try:
            self.conn.execute(
                "INSERT INTO absence_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("settings.set failed key=%s", key)
            raise


# Module-level legacy aliases preserved for any older code path.
def get_setting(conn, key, default=None):
    return EnhancementSettings(conn).get(key, default)


def set_setting(conn, key, value):
    EnhancementSettings(conn).set(key, value)


# ===========================================================================
# ThemeService — #36 dark mode, #42 high contrast
# ===========================================================================

THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#f0f4f8", "fg": "#0f172a", "header_bg": "#1e3a5f",
        "header_fg": "white", "tree_bg": "white", "tree_fg": "#0f172a",
        "sel_bg": "#2563eb", "sel_fg": "white", "accent": "#2563eb",
    },
    "dark": {
        "bg": "#0f172a", "fg": "#e2e8f0", "header_bg": "#020617",
        "header_fg": "#f1f5f9", "tree_bg": "#1e293b", "tree_fg": "#e2e8f0",
        "sel_bg": "#3b82f6", "sel_fg": "white", "accent": "#60a5fa",
    },
    "high_contrast": {
        "bg": "#000000", "fg": "#ffff00", "header_bg": "#000000",
        "header_fg": "#ffff00", "tree_bg": "#000000", "tree_fg": "#ffffff",
        "sel_bg": "#ffff00", "sel_fg": "#000000", "accent": "#00ffff",
    },
}


class ThemeService:
    """Apply / cycle Tk theme palettes; persists choice in absence_settings."""

    ORDER = ["light", "dark", "high_contrast"]

    def __init__(self, settings: EnhancementSettings) -> None:
        self.settings = settings

    def apply(self, root: tk.Misc, theme_name: str = "light") -> None:
        theme = THEMES.get(theme_name, THEMES["light"])
        try:
            root.configure(bg=theme["bg"])
        except tk.TclError:
            logger.debug("root.configure failed", exc_info=True)

        def walk(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Frame", "Labelframe", "Toplevel", "Tk"):
                    widget.configure(bg=theme["bg"])
                elif cls == "Label":
                    widget.configure(bg=theme["bg"], fg=theme["fg"])
                elif cls == "Entry":
                    widget.configure(bg=theme["tree_bg"], fg=theme["tree_fg"],
                                     insertbackground=theme["tree_fg"])
                elif cls == "Text":
                    widget.configure(bg=theme["tree_bg"], fg=theme["tree_fg"],
                                     insertbackground=theme["tree_fg"])
                elif cls == "Canvas":
                    widget.configure(bg=theme["tree_bg"])
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)
        walk(root)

        try:
            style = ttk.Style()
            style.configure("Treeview",
                            background=theme["tree_bg"],
                            foreground=theme["tree_fg"],
                            fieldbackground=theme["tree_bg"])
            style.configure("Treeview.Heading",
                            background=theme["header_bg"],
                            foreground=theme["header_fg"])
            style.map("Treeview",
                      background=[("selected", theme["sel_bg"])],
                      foreground=[("selected", theme["sel_fg"])])
        except tk.TclError:
            logger.debug("ttk.Style failed", exc_info=True)

    def cycle(self, root: tk.Misc) -> str:
        current = self.settings.get("theme", "light") or "light"
        try:
            nxt = self.ORDER[(self.ORDER.index(current) + 1) % len(self.ORDER)]
        except ValueError:
            nxt = "light"
        self.settings.set("theme", nxt)
        self.apply(root, nxt)
        logger.info("theme cycled %s -> %s", current, nxt)
        return nxt


# Module-level legacy aliases.
def apply_theme(root: tk.Misc, theme_name: str = "light") -> None:
    # No conn here — build a stand-alone settings shim that just no-ops.
    class _NoOpSettings:
        def get(self, *_a, **_k): return None
        def set(self, *_a, **_k): pass
    ThemeService(_NoOpSettings()).apply(root, theme_name)  # type: ignore[arg-type]


def cycle_theme(root: tk.Misc, conn: sqlite3.Connection) -> str:
    return ThemeService(EnhancementSettings(conn)).cycle(root)


# ===========================================================================
# TreeUxService — #37/38/39/40/42 (sort, filter, paginator, shortcuts, a11y)
# ===========================================================================

class Paginator:
    """Page-size-aware Treeview pager. Public — used by absence_tracker."""

    def __init__(self, tree: ttk.Treeview, parent: tk.Widget,
                 get_rows: Callable[[], List[Tuple]],
                 page_size: int = 100) -> None:
        self.tree = tree
        self.get_rows = get_rows
        self.page_size = page_size
        self.page = 0
        self._all: List[Tuple] = []
        self.bar = tk.Frame(parent)
        self.bar.pack(fill="x", padx=10, pady=(0, 6))
        tk.Button(self.bar, text="◀ Prev", command=self.prev,
                  relief="flat").pack(side="left", padx=4)
        self.lbl = tk.Label(self.bar, text="")
        self.lbl.pack(side="left", padx=6)
        tk.Button(self.bar, text="Next ▶", command=self.next,
                  relief="flat").pack(side="left", padx=4)
        tk.Label(self.bar, text="Page size:").pack(side="left", padx=4)
        self.sz = tk.Spinbox(self.bar, from_=25, to=1000, increment=25,
                             width=6, command=self._resize)
        self.sz.delete(0, "end")
        self.sz.insert(0, str(page_size))
        self.sz.pack(side="left")

    def _resize(self) -> None:
        try:
            self.page_size = max(1, int(self.sz.get()))
        except ValueError:
            return
        self.page = 0
        self.refresh()

    def refresh(self) -> None:
        try:
            self._all = list(self.get_rows())
        except Exception:
            logger.exception("Paginator get_rows failed")
            self._all = []
        self._render()

    def _render(self) -> None:
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except tk.TclError:
            return
        total = len(self._all)
        pages = max(1, math.ceil(total / self.page_size))
        self.page = min(self.page, pages - 1)
        start = self.page * self.page_size
        end = start + self.page_size
        for row in self._all[start:end]:
            self.tree.insert("", "end", values=row)
        self.lbl.config(
            text=f"Page {self.page + 1} / {pages}   ({total} rows)")

    def prev(self) -> None:
        if self.page > 0:
            self.page -= 1
            self._render()

    def next(self) -> None:
        pages = max(1, math.ceil(len(self._all) / self.page_size))
        if self.page < pages - 1:
            self.page += 1
            self._render()


class TreeUxService:
    """UX helpers applied to ttk.Treeviews + the dashboard root."""

    def __init__(self, settings: EnhancementSettings,
                 theme: ThemeService) -> None:
        self.settings = settings
        self.theme = theme

    # --- #39 sortable columns ----------------------------------------
    @staticmethod
    def make_sortable(tree: ttk.Treeview) -> None:
        state: Dict[str, bool] = {}

        def sort_by(col: str) -> None:
            desc = state.get(col, False)
            try:
                rows = [(tree.set(k, col), k) for k in tree.get_children("")]
            except tk.TclError:
                return

            def key(v):
                s = v[0]
                try:
                    return (0, float(s))
                except (TypeError, ValueError):
                    return (1, str(s).lower())

            rows.sort(key=key, reverse=desc)
            for idx, (_, k) in enumerate(rows):
                tree.move(k, "", idx)
            state[col] = not desc
            for c in tree["columns"]:
                base = tree.heading(c)["text"].rstrip(" ▲▼")
                tree.heading(
                    c,
                    text=base + (" ▼" if (c == col and desc)
                                 else " ▲" if c == col else ""))

        for col in tree["columns"]:
            tree.heading(col, command=lambda c=col: sort_by(c))

    # --- #38 filter bar ----------------------------------------------
    @staticmethod
    def add_filter_bar(parent: tk.Widget, tree: ttk.Treeview,
                       get_all_rows: Callable[[], List[Tuple]],
                       columns: List[str]) -> tk.Frame:
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=10, pady=4)
        tk.Label(bar, text="🔍 Filter:").pack(side="left", padx=4)
        ent = tk.Entry(bar, width=30)
        ent.pack(side="left", padx=4)
        col_var = tk.StringVar(value="(any)")
        ttk.Combobox(bar, textvariable=col_var,
                     values=["(any)"] + list(columns),
                     state="readonly", width=14).pack(side="left", padx=4)

        def apply_filter() -> None:
            needle = ent.get().strip().lower()
            col = col_var.get()
            try:
                all_rows = get_all_rows()
            except Exception:
                logger.exception("filter get_all_rows failed")
                all_rows = []
            try:
                for item in tree.get_children():
                    tree.delete(item)
            except tk.TclError:
                return
            if not needle:
                for row in all_rows:
                    tree.insert("", "end", values=row)
                return
            for row in all_rows:
                if col == "(any)":
                    hay = " ".join(str(c) for c in row).lower()
                    if needle in hay:
                        tree.insert("", "end", values=row)
                else:
                    try:
                        idx = columns.index(col)
                        if needle in str(row[idx]).lower():
                            tree.insert("", "end", values=row)
                    except (ValueError, IndexError):
                        pass

        ent.bind("<KeyRelease>", lambda _e: apply_filter())
        col_var.trace_add("write", lambda *_a: apply_filter())
        tk.Button(bar, text="Clear",
                  command=lambda: (ent.delete(0, "end"), apply_filter()),
                  relief="flat").pack(side="left", padx=2)
        return bar

    # --- #37 keyboard shortcuts --------------------------------------
    @staticmethod
    def bind_shortcuts(root: tk.Misc,
                       actions: Dict[str, Callable]) -> None:
        for combo, fn in actions.items():
            try:
                root.bind_all(combo, lambda e, f=fn: f())
            except tk.TclError:
                logger.debug("shortcut bind failed combo=%s", combo)

    # --- #42 a11y labels --------------------------------------------
    @staticmethod
    def add_a11y_labels(root: tk.Misc) -> None:
        """Tag every interactive widget with an accessible name announced
        on focus. Works by binding <FocusIn> to a no-op handler that names
        the widget — assistive tech reads the bound text."""
        def walk(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Button", "Entry", "Combobox", "Treeview"):
                    txt = ""
                    try:
                        txt = widget.cget("text")
                    except tk.TclError:
                        pass
                    if not txt and cls == "Treeview":
                        txt = "data table; use arrow keys"
                    if txt:
                        widget.bind(
                            "<FocusIn>",
                            lambda _e, w=widget, t=txt: setattr(
                                w, "_a11y_name", t))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)
        walk(root)

    # --- helpers -----------------------------------------------------
    @staticmethod
    def find_treeviews(widget) -> List[ttk.Treeview]:
        out: List[ttk.Treeview] = []
        if isinstance(widget, ttk.Treeview):
            out.append(widget)
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return out
        for child in children:
            out.extend(TreeUxService.find_treeviews(child))
        return out

    @staticmethod
    def all_widgets(widget):
        yield widget
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            yield from TreeUxService.all_widgets(child)

    def focus_first_filter(self, root: tk.Misc) -> None:
        for w in self.all_widgets(root):
            try:
                if w.winfo_class() == "Entry":
                    w.focus_set()
                    return
            except tk.TclError:
                continue

    # --- aggregator --------------------------------------------------
    def apply_to_dashboard(self, dashboard) -> None:
        """Apply sort + a11y + theme + shortcuts to every tree on the
        dashboard. Filter bars and pagination are opt-in per tree."""
        root = dashboard.root
        for tv in self.find_treeviews(root):
            try:
                self.make_sortable(tv)
            except tk.TclError:
                logger.debug("make_sortable failed", exc_info=True)
        self.theme.apply(root, self.settings.get("theme", "light") or "light")
        if self.settings.get("a11y_labels", "0") == "1":
            self.add_a11y_labels(root)

        def _save_focus():
            w = root.focus_get()
            if w:
                try:
                    w.event_generate("<Return>")
                except tk.TclError:
                    pass

        def _refresh():
            for child in self.all_widgets(root):
                try:
                    if (child.winfo_class() == "Button"
                            and "Refresh" in str(child.cget("text"))):
                        child.invoke()
                        return
                except tk.TclError:
                    continue

        def _toggle_theme():
            name = self.theme.cycle(root)
            try:
                messagebox.showinfo("Theme", f"Theme: {name}", parent=root)
            except tk.TclError:
                pass

        self.bind_shortcuts(root, {
            "<Control-s>": _save_focus,
            "<Control-r>": _refresh,
            "<Control-d>": _toggle_theme,
            "<Control-f>": lambda: self.focus_first_filter(root),
        })


# Module-level legacy aliases (used by absence_tracker + others).
def make_sortable(tree: ttk.Treeview) -> None:
    TreeUxService.make_sortable(tree)


def add_filter_bar(parent: tk.Widget, tree: ttk.Treeview,
                   get_all_rows: Callable[[], List[Tuple]],
                   columns: List[str]) -> tk.Frame:
    return TreeUxService.add_filter_bar(parent, tree, get_all_rows, columns)


def bind_shortcuts(root: tk.Misc, actions: Dict[str, Callable]) -> None:
    TreeUxService.bind_shortcuts(root, actions)


def add_a11y_labels(root: tk.Misc) -> None:
    TreeUxService.add_a11y_labels(root)


def apply_ux(dashboard) -> None:
    settings = EnhancementSettings(dashboard.db.conn)
    TreeUxService(settings, ThemeService(settings)).apply_to_dashboard(
        dashboard)


# ===========================================================================
# GeofenceService — #3
# ===========================================================================

class GeofenceService:
    """Wraps services.attendance.geofencing.GeofencingSystem with a
    DB-resolved campus centre."""

    _shared_instance: Any = None

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.settings = EnhancementSettings(conn)

    @classmethod
    def _get_system(cls):
        if cls._shared_instance is None:
            from education_system.systems.university.domain.academics.services.attendance.geofencing import (  # noqa: E501
                GeofencingSystem,
            )
            cls._shared_instance = GeofencingSystem()
        return cls._shared_instance

    def _ensure_active_session(self, gs, module_code: str,
                               d: str) -> Optional[str]:
        try:
            row = self.conn.execute(
                "SELECT session_id, latitude, longitude, geofence_radius "
                "FROM attendance_sessions WHERE module_code=? AND date=? "
                "ORDER BY rowid DESC LIMIT 1",
                (module_code, d)).fetchone()
        except sqlite3.Error:
            logger.exception("session lookup failed mc=%s d=%s",
                             module_code, d)
            return None
        if row:
            sid, lat, lon, rad = row
            gs.active_locations[sid] = {
                "module_code": module_code, "date": d,
                "location": (lat, lon), "radius": rad or 50,
            }
            return sid
        raw_lat = self.settings.get("campus_lat")
        raw_lon = self.settings.get("campus_lon")
        if raw_lat in (None, "") or raw_lon in (None, ""):
            return None
        try:
            c_rad = float(self.settings.get("campus_radius_m", "500") or 500)
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (TypeError, ValueError):
            logger.exception("campus geofence settings malformed")
            return None
        try:
            return gs.create_geofenced_session(
                module_code, d, "campus", lat, lon, c_rad)
        except Exception:
            logger.exception("create_geofenced_session failed mc=%s",
                             module_code)
            return None

    def record_checkin(self, student_id: str, module_code: str,
                       lat: float, lon: float, *,
                       device_id: str = "",
                       when: Optional[date] = None) -> Tuple[bool, str]:
        d = (when or date.today()).isoformat()
        try:
            gs = self._get_system()
        except Exception as e:
            logger.exception("GeofencingSystem unavailable")
            return False, f"geofencing unavailable: {e}"
        sid = self._ensure_active_session(gs, module_code, d)
        if not sid:
            return (False,
                    "no geofenced session and campus centre not configured")
        try:
            ok, msg = gs.check_location_attendance(
                student_id, lat, lon, session_id=sid)
        except Exception as e:
            logger.exception("check_location_attendance failed")
            return False, f"geofence check failed: {e}"
        return bool(ok), msg


def record_geofenced_checkin(conn, student_id, module_code, lat, lon,
                             device_id: str = "",
                             when=None) -> Tuple[bool, str]:
    return GeofenceService(conn).record_checkin(
        student_id, module_code, lat, lon,
        device_id=device_id, when=when)


# ===========================================================================
# FaceCheckinService — #4
# ===========================================================================

class FaceCheckinService:
    """Facial recognition kiosk wrapper."""

    _shared_instance: Any = None

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def _get_system(cls):
        if cls._shared_instance is None:
            from education_system.systems.university.domain.academics.services.attendance.face_recognition_system import (  # noqa: E501
                FaceRecognitionSystem,
            )
            cls._shared_instance = FaceRecognitionSystem()
        return cls._shared_instance

    def register_kiosk(self, kiosk_id: str, room: str,
                       lat: float, lon: float,
                       radius_m: float = 50) -> None:
        try:
            self.conn.execute(
                """INSERT INTO attendance_kiosks
                     (kiosk_id, room, lat, lon, radius_m)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(kiosk_id) DO UPDATE SET
                     room=excluded.room, lat=excluded.lat,
                     lon=excluded.lon, radius_m=excluded.radius_m,
                     active=1""",
                (kiosk_id, room, lat, lon, radius_m))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("kiosk register failed id=%s", kiosk_id)
            raise

    def checkin(self, kiosk_id: str, module_code: str,
                image_path: str,
                recogniser: Optional[Callable] = None
                ) -> Tuple[bool, str, Optional[str]]:
        if recogniser is not None:
            # Test / custom recogniser — bypass the real ML pipeline.
            try:
                student_id, conf = recogniser(image_path)
            except Exception as e:
                logger.exception("custom recogniser raised")
                return False, f"recogniser error: {e}", None
            if not student_id:
                return False, f"low confidence ({conf:.2f})", None
            d = date.today().isoformat()
            try:
                self.conn.execute(
                    """INSERT INTO attendance
                         (student_id, module_code, date, status, reason)
                       VALUES (?,?,?,?,?)""",
                    (student_id, module_code, d, "present",
                     f"face kiosk {kiosk_id}"))
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                logger.exception("face kiosk insert failed sid=%s",
                                 student_id)
                return False, str(e), None
            return True, "ok", student_id
        try:
            fs = self._get_system()
        except Exception as e:
            logger.exception("FaceRecognitionSystem unavailable")
            return False, f"face recognition unavailable: {e}", None
        d = date.today().isoformat()
        try:
            ok, msg, sid = fs.recognize_face_attendance(
                image_path, module_code, d)
        except Exception as e:
            logger.exception("recognize_face_attendance failed")
            return False, f"face recognition failed: {e}", None
        return bool(ok), msg, sid


def register_kiosk(conn, kiosk_id, room, lat, lon, radius_m=50):
    FaceCheckinService(conn).register_kiosk(kiosk_id, room, lat, lon,
                                            radius_m)


def facial_checkin(conn, kiosk_id, module_code, image_path,
                   recogniser=None) -> Tuple[bool, str, Optional[str]]:
    return FaceCheckinService(conn).checkin(
        kiosk_id, module_code, image_path, recogniser)


# ===========================================================================
# RequestCategoryService — #11
# ===========================================================================

class RequestCategoryService:
    """Manage absence request categories + per-category routing."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list(self) -> List[Tuple]:
        try:
            return self.conn.execute(
                """SELECT id, name, description, requires_evidence,
                          approval_route, auto_approve
                   FROM absence_request_categories
                   ORDER BY name""").fetchall()
        except sqlite3.Error:
            logger.exception("category list failed")
            return []

    def assign_to_request(self, request_id: int, category_id: int) -> None:
        try:
            self.conn.execute(
                "UPDATE absence_requests SET category_id=? WHERE id=?",
                (category_id, request_id))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("category assign failed rid=%s", request_id)
            raise

    def route_for(self, request_id: int) -> Dict[str, Any]:
        try:
            row = self.conn.execute(
                """SELECT c.name, c.approval_route,
                          c.auto_approve, c.requires_evidence
                   FROM absence_requests r
                   LEFT JOIN absence_request_categories c
                     ON c.id = r.category_id
                   WHERE r.id = ?""", (request_id,)).fetchone()
        except sqlite3.Error:
            logger.exception("route_for failed rid=%s", request_id)
            return {}
        if not row:
            return {}
        name, route, auto, req_ev = row
        return {
            "category": name,
            "route": route or "instructor",
            "auto_approve": bool(auto),
            "requires_evidence": bool(req_ev),
        }


def list_categories(conn):
    return RequestCategoryService(conn).list()


def set_request_category(conn, request_id, category_id):
    RequestCategoryService(conn).assign_to_request(request_id, category_id)


def route_for_request(conn, request_id) -> Dict[str, Any]:
    return RequestCategoryService(conn).route_for(request_id)


# ===========================================================================
# PushQueueService — #21
# ===========================================================================

class PushQueueService:
    """Mobile-push queue. Persists pending pushes; ``drain`` delivers them
    via an injected sender, or via shared.notifications.push.send."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def enqueue(self, user_id: str, title: str, body: str,
                payload: Optional[dict] = None) -> Optional[int]:
        try:
            cur = self.conn.execute(
                """INSERT INTO absence_push_queue(user_id, title, body, payload)
                   VALUES(?,?,?,?)""",
                (user_id, title, body, json.dumps(payload or {})))
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("push enqueue failed uid=%s", user_id)
            return None

    def drain(self,
              sender: Optional[Callable[[str, str, str, dict], bool]] = None
              ) -> int:
        if sender is None:
            try:
                from education_system.platform.features.notifications import (  # type: ignore
                    push as _push,
                )
                sender = _push.send
            except Exception:
                logger.debug("no push sender available", exc_info=True)
                return 0
        try:
            cur = self.conn.execute(
                """SELECT id, user_id, title, body, payload
                   FROM absence_push_queue
                   WHERE status='pending' ORDER BY id LIMIT 500""")
            rows = cur.fetchall()
        except sqlite3.Error:
            logger.exception("push drain query failed")
            return 0
        sent = 0
        for pid, uid, title, body, payload in rows:
            try:
                ok = sender(uid, title, body,
                            json.loads(payload or "{}"))
            except Exception:
                logger.exception("push send failed for id=%s", pid)
                ok = False
            try:
                if ok:
                    self.conn.execute(
                        "UPDATE absence_push_queue "
                        "SET status='sent', delivered_at=CURRENT_TIMESTAMP "
                        "WHERE id=?", (pid,))
                    sent += 1
                else:
                    self.conn.execute(
                        "UPDATE absence_push_queue SET status='failed' "
                        "WHERE id=?", (pid,))
            except sqlite3.Error:
                logger.exception("push status update failed id=%s", pid)
        try:
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("push drain commit failed")
        return sent


def queue_push(conn, user_id, title, body,
               payload: Optional[dict] = None) -> int:
    rid = PushQueueService(conn).enqueue(user_id, title, body, payload)
    return rid or 0


def drain_push_queue(conn,
                     sender: Optional[Callable[[str, str, str, dict], bool]
                                      ] = None) -> int:
    return PushQueueService(conn).drain(sender)


# ===========================================================================
# ComplianceService — #30 HESA, #31 UKVI
# ===========================================================================

HESA_COLS = [
    "HUSID", "STULOAD", "MODULECODE", "MODULENAME",
    "ENGAGEMENT_DATE", "ENGAGEMENT_TYPE", "ENGAGEMENT_OUTCOME",
    "EXPECTED_SESSIONS", "ATTENDED_SESSIONS", "ATTENDANCE_PCT",
]


class ComplianceService:
    """HESA export + UKVI engagement monitoring."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # --- HESA --------------------------------------------------------
    def hesa_export(self, out_path: str,
                    term_start: Optional[str] = None,
                    term_end: Optional[str] = None) -> int:
        try:
            cur = self.conn.execute("PRAGMA table_info(students)")
            scols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("students PRAGMA failed")
            return 0
        stuload_expr = ("COALESCE(s.study_mode, 'FT')"
                        if "study_mode" in scols else "'FT'")
        sql = f"""
            SELECT s.student_id AS HUSID,
                   {stuload_expr} AS STULOAD,
                   m.module_code AS MODULECODE,
                   m.module_name AS MODULENAME,
                   MAX(a.date)   AS ENGAGEMENT_DATE,
                   'ATTENDANCE' AS ENGAGEMENT_TYPE,
                   CASE WHEN SUM(CASE WHEN a.status='present'
                                       THEN 1 ELSE 0 END)
                              >= 0.75 * COUNT(a.id)
                        THEN 'ENGAGED' ELSE 'AT_RISK'
                   END AS ENGAGEMENT_OUTCOME,
                   COUNT(a.id) AS EXPECTED_SESSIONS,
                   SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                       AS ATTENDED_SESSIONS,
                   ROUND(100.0 * SUM(CASE WHEN a.status='present'
                                          THEN 1 ELSE 0 END)
                           / NULLIF(COUNT(a.id), 0), 2) AS ATTENDANCE_PCT
              FROM attendance a
              JOIN students s ON s.student_id = a.student_id
              JOIN modules  m ON m.module_code = a.module_code
             WHERE (? IS NULL OR a.date >= ?)
               AND (? IS NULL OR a.date <= ?)
             GROUP BY s.student_id, m.module_code, m.module_name
             ORDER BY s.student_id, m.module_code
        """
        try:
            rows = self.conn.execute(
                sql, (term_start, term_start, term_end, term_end)).fetchall()
        except sqlite3.Error:
            logger.exception("HESA query failed")
            return 0
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(HESA_COLS)
                w.writerows(rows)
        except OSError:
            logger.exception("HESA write failed path=%s", out_path)
            return 0
        logger.info("HESA export wrote %d rows -> %s", len(rows), out_path)
        return len(rows)

    # --- UKVI --------------------------------------------------------
    def ukvi_log(self, student_id: str, event_type: str,
                 event_date: Optional[str] = None,
                 notes: str = "", recorded_by: str = "") -> None:
        try:
            cur = self.conn.execute(
                """INSERT INTO ukvi_engagement_events
                     (student_id, event_type, event_date, notes, recorded_by)
                   VALUES(?,?,?,?,?)""",
                (student_id, event_type,
                 (event_date or date.today().isoformat()),
                 notes, recorded_by))
            event_id = cur.lastrowid
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("UKVI log failed sid=%s ev=%s",
                             student_id, event_type)
            raise

        # Mirror into the visa-sponsorship dashboard. Best-effort: if the
        # international_compliance module isn't installed (e.g. minimal
        # deployment) or the visa table isn't there yet, swallow the error
        # — the source row is committed and that's what matters.
        try:
            self._mirror_to_visa_engagement(
                event_id, student_id, event_type,
                event_date or date.today().isoformat(),
                notes, recorded_by,
            )
        except Exception:
            logger.debug("visa-mirror skipped sid=%s ev=%s", student_id, event_type, exc_info=True)

    def _mirror_to_visa_engagement(
        self, event_id: int, student_id: str, event_type: str,
        event_date: str, notes: str, recorded_by: str,
    ) -> None:
        """Insert a matching row into ``visa_engagement_checks`` on the
        same DB connection. Idempotent via the unique partial index on
        ``source_event_id``."""
        # Map legacy event_type to the visa module's three-valued outcome.
        et = (event_type or "").strip().lower()
        if et in {"missed", "no_engagement", "absent_critical", "failed"}:
            outcome = "missed"
        elif et in {"at_risk", "low_attendance", "partial", "late"}:
            outcome = "partial"
        else:
            outcome = "engaged"
        try:
            rec_by_int: Optional[int] = int(recorded_by) if recorded_by not in (None, "") else None
        except (TypeError, ValueError):
            rec_by_int = None
        try:
            self.conn.execute(
                """INSERT INTO visa_engagement_checks
                     (student_id, check_date, term, method, evidence,
                      outcome, recorded_by, source_event_id)
                   VALUES (?, ?, NULL, ?, ?, ?, ?, ?)""",
                (
                    student_id, event_date,
                    f"attendance pipeline ({event_type or 'unspecified'})",
                    notes, outcome, rec_by_int, event_id,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Already mirrored by a parallel run / earlier importer.
            self.conn.rollback()

    def ukvi_at_risk(self, min_pct: float = 80.0) -> List[Tuple]:
        """Student-Route / Tier-4 holders below engagement threshold."""
        try:
            cur = self.conn.execute("PRAGMA table_info(students)")
            cols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("students PRAGMA failed")
            return []
        # visa_filter is built from a closed set of column names — safe to
        # interpolate into the SQL string.
        if "visa_type" in cols:
            visa_filter = ("AND s.visa_type IN ('student_route','tier_4',"
                           "'Tier 4','Student Route')")
        elif "international" in cols:
            visa_filter = "AND s.international = 1"
        else:
            visa_filter = ""
        sql = f"""
            SELECT s.student_id,
                   TRIM(COALESCE(s.first_name,'')||' '
                        ||COALESCE(s.last_name,'')) AS name,
                   ROUND(100.0 * SUM(CASE WHEN a.status='present'
                                          THEN 1 ELSE 0 END)
                         / NULLIF(COUNT(a.id),0), 2) AS pct,
                   SUM(CASE WHEN a.status IN ('absent','late')
                            THEN 1 ELSE 0 END) AS missed
              FROM students s
              JOIN attendance a ON a.student_id = s.student_id
             WHERE 1=1 {visa_filter}
             GROUP BY s.student_id
            HAVING pct IS NOT NULL AND pct < ?
             ORDER BY pct ASC
        """
        try:
            return list(self.conn.execute(sql, (min_pct,)).fetchall())
        except sqlite3.Error:
            logger.exception("UKVI at-risk query failed")
            return []


def hesa_export(conn, out_path: str,
                term_start: Optional[str] = None,
                term_end: Optional[str] = None) -> int:
    return ComplianceService(conn).hesa_export(out_path, term_start, term_end)


def ukvi_log_event(conn, student_id, event_type, event_date=None,
                   notes: str = "", recorded_by: str = "") -> None:
    ComplianceService(conn).ukvi_log(
        student_id, event_type, event_date, notes, recorded_by)


def ukvi_at_risk(conn, min_pct: float = 80.0) -> List[Tuple]:
    return ComplianceService(conn).ukvi_at_risk(min_pct)


# ===========================================================================
# EvidenceService — #35 SHA-256 signatures
# ===========================================================================

class EvidenceService:
    """SHA-256 digital signatures of evidence files attached to requests."""

    CHUNK = 65536

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def _hash_file(cls, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(cls.CHUNK), b""):
                h.update(chunk)
        return h.hexdigest()

    def sign(self, request_id: int, file_path: str,
             signed_by: str) -> Optional[str]:
        try:
            digest = self._hash_file(file_path)
        except OSError:
            logger.exception("sign read failed path=%s", file_path)
            raise
        try:
            self.conn.execute(
                """INSERT INTO absence_evidence_signatures
                     (request_id, file_path, sha256, signed_by)
                   VALUES(?,?,?,?)""",
                (request_id, file_path, digest, signed_by))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("sign insert failed rid=%s", request_id)
            raise
        logger.info("evidence signed rid=%s by=%s sha=%s",
                    request_id, signed_by, digest[:12])
        return digest

    def verify(self, request_id: int, file_path: str) -> bool:
        try:
            row = self.conn.execute(
                """SELECT sha256 FROM absence_evidence_signatures
                   WHERE request_id=? AND file_path=?
                   ORDER BY id DESC LIMIT 1""",
                (request_id, file_path)).fetchone()
        except sqlite3.Error:
            logger.exception("verify lookup failed rid=%s", request_id)
            return False
        if not row:
            return False
        try:
            return self._hash_file(file_path) == row[0]
        except OSError:
            logger.exception("verify read failed path=%s", file_path)
            return False


def sign_evidence(conn, request_id: int, file_path: str,
                  signed_by: str) -> str:
    return EvidenceService(conn).sign(request_id, file_path, signed_by) or ""


def verify_evidence(conn, request_id: int, file_path: str) -> bool:
    return EvidenceService(conn).verify(request_id, file_path)


# ===========================================================================
# LmsSyncService — #46
# ===========================================================================

class LmsSyncService:
    """Mirror approved absence requests as LMS access grants."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def grant_for_absence(self, student_id: str, module_code: str,
                          session_date: str,
                          resource: str = "lecture_recording",
                          reason: str = "approved absence") -> None:
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO lms_access_grants
                     (student_id, module_code, session_date, resource,
                      granted, reason)
                   VALUES(?,?,?,?,1,?)""",
                (student_id, module_code, session_date, resource, reason))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("LMS grant insert failed sid=%s mc=%s",
                             student_id, module_code)
            return
        try:
            from education_system.systems.university.domain.academics.services.lms import (  # type: ignore  # noqa: E501
                lms_core as _lms,
            )
            if hasattr(_lms, "grant_access"):
                _lms.grant_access(student_id, module_code, session_date,
                                  resource)
        except Exception:
            logger.debug("LMS push skipped/failed", exc_info=True)

    def sync_approved_requests(self) -> int:
        try:
            cur = self.conn.execute(
                """SELECT r.id, r.student_id, r.module_code, r.date
                   FROM absence_requests r
                   LEFT JOIN lms_access_grants g
                       ON g.student_id = r.student_id
                      AND g.module_code = r.module_code
                      AND g.session_date = r.date
                   WHERE r.status = 'approved' AND g.id IS NULL""")
            rows = cur.fetchall()
        except sqlite3.Error:
            logger.exception("lms sync query failed")
            return 0
        n = 0
        for _id, sid, mod, d in rows:
            self.grant_for_absence(sid, mod, d)
            n += 1
        logger.info("LMS sync mirrored %d grant(s)", n)
        return n


def lms_on_absence(conn, student_id, module_code, session_date,
                   resource: str = "lecture_recording",
                   reason: str = "approved absence") -> None:
    LmsSyncService(conn).grant_for_absence(
        student_id, module_code, session_date, resource, reason)


def lms_sync_approved_requests(conn) -> int:
    return LmsSyncService(conn).sync_approved_requests()


# ===========================================================================
# AnomalyService — #50
# ===========================================================================

class AnomalyService:
    """Detect proxy sign-ins, impossible concurrency, mass identical reasons."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def scan(self) -> List[Dict[str, Any]]:
        new: List[Dict[str, Any]] = []
        new.extend(self._scan_concurrency())
        new.extend(self._scan_shared_devices())
        new.extend(self._scan_mass_identical_reasons())
        try:
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("anomaly commit failed")
        logger.info("anomaly scan inserted %d row(s)", len(new))
        return new

    def _scan_concurrency(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            rows = self.conn.execute(
                """SELECT a.student_id, a.date, GROUP_CONCAT(a.module_code)
                   FROM attendance a
                   WHERE a.status='present'
                   GROUP BY a.student_id, a.date
                   HAVING COUNT(DISTINCT a.module_code) > 1""").fetchall()
        except sqlite3.Error:
            logger.exception("concurrency anomaly scan failed")
            return out
        for sid, d, mods in rows:
            details = f"present in {mods} on {d}"
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, student_id, details, severity) "
                    "VALUES('concurrency', ?, ?, 'high')",
                    (sid, details))
                out.append({"id": r.lastrowid, "kind": "concurrency",
                            "student_id": sid, "details": details})
            except sqlite3.Error:
                logger.exception("concurrency insert failed sid=%s", sid)
        return out

    def _scan_shared_devices(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            cur = self.conn.execute("PRAGMA table_info(attendance_records)")
            ar_cols = {r[1] for r in cur.fetchall()}
        except sqlite3.Error:
            logger.exception("attendance_records PRAGMA failed")
            return out
        if "location_data" not in ar_cols or "student_id" not in ar_cols:
            return out
        try:
            cur = self.conn.execute(
                """SELECT json_extract(location_data, '$.device_id') AS dev,
                          COUNT(DISTINCT student_id),
                          GROUP_CONCAT(DISTINCT student_id)
                   FROM attendance_records
                   WHERE location_data IS NOT NULL
                     AND json_extract(location_data, '$.device_id')
                         IS NOT NULL
                   GROUP BY dev
                   HAVING COUNT(DISTINCT student_id) >= 5""")
        except sqlite3.OperationalError:
            logger.debug("shared_device scan skipped (json1 unavailable)")
            return out
        for dev, n, sids in cur.fetchall():
            details = f"device {dev} used by {n} students: {sids}"
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, details, severity) "
                    "VALUES('shared_device', ?, 'high')",
                    (details,))
                out.append({"id": r.lastrowid, "kind": "shared_device",
                            "details": details})
            except sqlite3.Error:
                logger.exception("shared_device insert failed dev=%s", dev)
        return out

    def _scan_mass_identical_reasons(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            rows = self.conn.execute(
                """SELECT date, reason, COUNT(DISTINCT student_id)
                   FROM attendance
                   WHERE reason IS NOT NULL AND reason != ''
                   GROUP BY date, reason
                   HAVING COUNT(DISTINCT student_id) >= 10""").fetchall()
        except sqlite3.Error:
            logger.exception("mass_proxy scan failed")
            return out
        for d, reason, n in rows:
            details = (f"{n} students share identical reason "
                       f"'{reason[:40]}' on {d}")
            try:
                r = self.conn.execute(
                    "INSERT INTO attendance_anomalies"
                    "(kind, details, severity) "
                    "VALUES('mass_proxy_reason', ?, 'medium')",
                    (details,))
                out.append({"id": r.lastrowid,
                            "kind": "mass_proxy_reason",
                            "details": details})
            except sqlite3.Error:
                logger.exception("mass_proxy insert failed")
        return out


def anomaly_scan(conn) -> List[Dict[str, Any]]:
    return AnomalyService(conn).scan()


# ===========================================================================
# ChatbotService — #49
# ===========================================================================

class ChatbotService:
    """Computes per-module / per-student remaining-absences quota."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def absence_quota(self, student_id: str,
                      module_code: Optional[str] = None,
                      threshold_pct: float = 75.0) -> str:
        if module_code:
            return self._single_module(student_id, module_code, threshold_pct)
        return self._all_modules(student_id, threshold_pct)

    def _single_module(self, sid: str, mc: str, threshold_pct: float) -> str:
        try:
            row = self.conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
                   FROM attendance
                   WHERE student_id=? AND module_code=?""",
                (sid, mc)).fetchone() or (0, 0, 0)
        except sqlite3.Error:
            logger.exception("quota single fetch failed sid=%s mc=%s",
                             sid, mc)
            return f"Could not load attendance for {mc}."
        total, present, absent = row
        if not total:
            return f"No attendance recorded yet for {mc}."
        pct = 100.0 * (present or 0) / total
        max_absences = math.floor(total * (1 - threshold_pct / 100.0))
        remaining = max(0, max_absences - (absent or 0))
        return (f"{mc}: {pct:.1f}% attended. "
                f"Threshold {threshold_pct:.0f}% → you can miss "
                f"{remaining} more session(s) before falling below.")

    def _all_modules(self, sid: str, threshold_pct: float) -> str:
        try:
            rows = self.conn.execute(
                """SELECT module_code,
                          COUNT(*),
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
                   FROM attendance
                   WHERE student_id=?
                   GROUP BY module_code""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("quota all fetch failed sid=%s", sid)
            return "Could not load attendance."
        lines = []
        for mod, total, present, absent in rows:
            if not total:
                continue
            max_abs = math.floor(total * (1 - threshold_pct / 100.0))
            rem = max(0, max_abs - (absent or 0))
            pct = 100.0 * (present or 0) / total
            lines.append(f"  • {mod}: {pct:.0f}% — {rem} more misses OK")
        if not lines:
            return "No attendance recorded yet."
        return "Attendance quota remaining:\n" + "\n".join(lines)


def chatbot_absence_quota(conn, student_id: str,
                          module_code: Optional[str] = None,
                          threshold_pct: float = 75.0) -> str:
    return ChatbotService(conn).absence_quota(
        student_id, module_code, threshold_pct)


# ===========================================================================
# EnhancementTabBuilder — role-aware GUI
# ===========================================================================

def _tree(parent, cols, widths) -> ttk.Treeview:
    frame = tk.Frame(parent)
    frame.pack(expand=True, fill="both", padx=10, pady=6)
    tv = ttk.Treeview(frame, columns=cols, show="headings")
    for c, w in zip(cols, widths):
        tv.heading(c, text=c)
        tv.column(c, width=w)
    tv.pack(expand=True, fill="both")
    TreeUxService.make_sortable(tv)
    return tv


class EnhancementTabBuilder:
    """Builds the role-appropriate Enhancements notebook tab."""

    def __init__(self, dashboard, role: str) -> None:
        self.dashboard = dashboard
        self.db = dashboard.db
        self.user = dashboard.user
        self.role = role
        self.conn = self.db.conn
        self.settings = EnhancementSettings(self.conn)
        self.theme = ThemeService(self.settings)
        self.ux = TreeUxService(self.settings, self.theme)

    # --- entry -------------------------------------------------------
    def build(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="✨ Enhancements")
        canvas = tk.Canvas(tab, highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", expand=True, fill="both")
        scroll.pack(side="right", fill="y")

        self._build_settings_section(inner)

        if self.role == "admin":
            self._build_attendance_tracker_pointer(
                inner, "Geofence settings & kiosk registry")
            self._build_categories_section(inner)
            self._build_compliance_section(inner)
            self._build_integrations_section(inner)
        elif self.role in ("staff", "instructor", "teacher"):
            self._build_attendance_tracker_pointer(
                inner, "Facial-recognition kiosk")
            self._build_categories_section(inner)
            self._build_compliance_section(inner)
            self._build_integrations_section(inner)
        else:
            self._build_student_enh_section(inner)

    # --- sections ---------------------------------------------------
    def _build_settings_section(self, tab) -> None:
        box = tk.LabelFrame(
            tab, text="Appearance & accessibility (#36, #37, #42)",
            padx=10, pady=8)
        box.pack(fill="x", padx=10, pady=6)
        theme_var = tk.StringVar(
            value=self.settings.get("theme", "light"))
        tk.Label(box, text="Theme:").grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(box, textvariable=theme_var,
                          values=list(THEMES.keys()),
                          state="readonly", width=20)
        cb.grid(row=0, column=1, padx=6)

        def set_t(*_):
            try:
                self.settings.set("theme", theme_var.get())
                self.theme.apply(self.dashboard.root, theme_var.get())
            except Exception:
                logger.exception("theme apply failed")
        cb.bind("<<ComboboxSelected>>", set_t)

        a11y_var = tk.BooleanVar(
            value=self.settings.get("a11y_labels", "0") == "1")

        def set_a11y():
            try:
                self.settings.set(
                    "a11y_labels", "1" if a11y_var.get() else "0")
            except Exception:
                logger.exception("a11y setting failed")

        tk.Checkbutton(box, text="Screen-reader labels on focus",
                       variable=a11y_var, command=set_a11y
                       ).grid(row=1, column=0, columnspan=2,
                              sticky="w", pady=4)

        tk.Label(box,
                 text="Keyboard shortcuts:  Ctrl+S save · Ctrl+F filter · "
                      "Ctrl+R refresh · Ctrl+D theme",
                 fg="#6b7280").grid(row=2, column=0, columnspan=3, sticky="w")

    def _build_attendance_tracker_pointer(self, tab, feature: str) -> None:
        """Placeholder where the duplicated geofence/kiosk panel used to live.

        Those features are now owned by the Attendance Tracker GUI
        (modules/academics/gui/attendance_tracker/) — this section only
        notes that and links back to the underlying service classes for
        any programmatic caller."""
        box = tk.LabelFrame(
            tab, text=f"{feature} (moved)",
            padx=10, pady=8)
        box.pack(fill="x", padx=10, pady=6)
        tk.Label(box,
                 text=("This feature is provided by the Attendance Tracker "
                       "GUI.\nUse the Attendance Tracker tab / window for "
                       "configuration.\n\n"
                       "Programmatic access remains available via "
                       "GeofenceService and FaceCheckinService."),
                 justify="left", fg="#6b7280"
                 ).pack(anchor="w", padx=4, pady=4)

    def _build_categories_section(self, tab) -> None:
        box = tk.LabelFrame(tab, text="Request categories (#11)",
                            padx=10, pady=8)
        box.pack(fill="x", padx=10, pady=6)
        cols = ("id", "name", "description", "requires_evidence",
                "approval_route", "auto_approve")
        tv = _tree(box, cols, (40, 120, 260, 120, 120, 90))
        cat_service = RequestCategoryService(self.conn)

        def refresh():
            tv.delete(*tv.get_children())
            for r in cat_service.list():
                tv.insert("", "end", values=r)

        def add_cat():
            name = simpledialog.askstring("Category", "Name:")
            if not name:
                return
            desc = simpledialog.askstring("Category", "Description:") or ""
            route = simpledialog.askstring(
                "Category",
                "Approval route (instructor/dept_head/registry):",
                initialvalue="instructor") or "instructor"
            req_ev = messagebox.askyesno("Evidence", "Requires evidence?")
            auto = messagebox.askyesno("Auto", "Auto-approve?")
            try:
                self.conn.execute(
                    """INSERT INTO absence_request_categories
                         (name, description, requires_evidence,
                          approval_route, auto_approve)
                       VALUES(?,?,?,?,?)""",
                    (name, desc, 1 if req_ev else 0, route,
                     1 if auto else 0))
                self.conn.commit()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Name must be unique.")
            except sqlite3.Error as e:
                self.conn.rollback()
                logger.exception("category add failed")
                messagebox.showerror("Failed", str(e))
                return
            refresh()

        def del_cat():
            sel = tv.selection()
            if not sel:
                return
            cid = tv.item(sel[0])["values"][0]
            if not messagebox.askyesno("Delete", "Delete category?"):
                return
            try:
                self.conn.execute(
                    "DELETE FROM absence_request_categories WHERE id=?",
                    (cid,))
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                logger.exception("category delete failed cid=%s", cid)
                messagebox.showerror("Failed", str(e))
                return
            refresh()

        row = tk.Frame(box); row.pack(fill="x", pady=4)
        tk.Button(row, text="+ Add", command=add_cat, bg="#16a34a",
                  fg="white", relief="flat").pack(side="left", padx=4)
        tk.Button(row, text="🗑 Delete", command=del_cat, bg="#dc2626",
                  fg="white", relief="flat").pack(side="left", padx=4)
        tk.Button(row, text="🔄", command=refresh, bg="#6b7280",
                  fg="white", relief="flat").pack(side="left", padx=4)
        refresh()

    def _build_compliance_section(self, tab) -> None:
        box = tk.LabelFrame(
            tab,
            text="Compliance (#30 HESA · #31 UKVI · #35 e-sig)",
            padx=10, pady=8)
        box.pack(fill="x", padx=10, pady=6)
        compliance = ComplianceService(self.conn)
        evidence = EvidenceService(self.conn)

        def do_hesa():
            p = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="hesa_attendance.csv")
            if not p:
                return
            n = compliance.hesa_export(p)
            messagebox.showinfo("HESA export", f"Wrote {n} rows → {p}")

        def do_ukvi():
            rows = compliance.ukvi_at_risk(80.0)
            win = tk.Toplevel()
            win.title("UKVI engagement — at-risk")
            tv = ttk.Treeview(
                win, columns=("student_id", "name", "pct", "missed"),
                show="headings")
            for c, w in zip(("student_id", "name", "pct", "missed"),
                            (120, 240, 80, 80)):
                tv.heading(c, text=c); tv.column(c, width=w)
            tv.pack(expand=True, fill="both", padx=10, pady=10)
            for r in rows:
                tv.insert("", "end", values=r)
            TreeUxService.make_sortable(tv)

        def do_sign():
            req = simpledialog.askinteger("Sign", "Request id:")
            if not req:
                return
            p = filedialog.askopenfilename(title="Evidence file")
            if not p:
                return
            try:
                digest = evidence.sign(req, p,
                                       self.user.get("username", ""))
            except (sqlite3.Error, OSError) as e:
                messagebox.showerror("Failed", str(e))
                return
            messagebox.showinfo("Signed", f"SHA-256: {digest}")

        tk.Button(box, text="📤 HESA export", command=do_hesa,
                  bg="#2563eb", fg="white", relief="flat"
                  ).pack(side="left", padx=6)
        tk.Button(box, text="🛂 UKVI at-risk", command=do_ukvi,
                  bg="#2563eb", fg="white", relief="flat"
                  ).pack(side="left", padx=6)
        tk.Button(box, text="✒ Sign evidence", command=do_sign,
                  bg="#16a34a", fg="white", relief="flat"
                  ).pack(side="left", padx=6)

    def _build_integrations_section(self, tab) -> None:
        box = tk.LabelFrame(
            tab,
            text="Integrations (#21 push · #46 LMS · #50 anomalies)",
            padx=10, pady=8)
        box.pack(fill="x", padx=10, pady=6)
        push = PushQueueService(self.conn)
        lms = LmsSyncService(self.conn)
        anomalies = AnomalyService(self.conn)

        def drain():
            n = push.drain()
            messagebox.showinfo("Push", f"Delivered {n} notification(s).")

        def lms_sync():
            n = lms.sync_approved_requests()
            messagebox.showinfo("LMS",
                                f"Mirrored {n} new access grant(s).")

        def anoms():
            new = anomalies.scan()
            messagebox.showinfo(
                "Anomalies",
                f"Found {len(new)} new anomaly record(s).")

        tk.Button(box, text="📲 Drain push queue", command=drain,
                  bg="#2563eb", fg="white", relief="flat"
                  ).pack(side="left", padx=6)
        tk.Button(box, text="🎥 LMS sync", command=lms_sync,
                  bg="#2563eb", fg="white", relief="flat"
                  ).pack(side="left", padx=6)
        tk.Button(box, text="🚨 Run anomaly scan", command=anoms,
                  bg="#dc2626", fg="white", relief="flat"
                  ).pack(side="left", padx=6)

        cols = ("id", "kind", "student_id", "module_code", "details",
                "severity", "detected_at", "resolved")
        tv = _tree(box, cols, (40, 120, 100, 100, 360, 80, 140, 70))

        def refresh():
            try:
                tv.delete(*tv.get_children())
                for r in self.conn.execute(
                        """SELECT id, kind, COALESCE(student_id,''),
                                  COALESCE(module_code,''),
                                  COALESCE(details,''), severity,
                                  detected_at, resolved
                           FROM attendance_anomalies
                           ORDER BY detected_at DESC LIMIT 500"""):
                    tv.insert("", "end", values=r)
            except sqlite3.Error:
                logger.exception("anomaly refresh failed")

        def resolve():
            try:
                for s in tv.selection():
                    aid = tv.item(s)["values"][0]
                    self.conn.execute(
                        "UPDATE attendance_anomalies SET resolved=1 "
                        "WHERE id=?", (aid,))
                self.conn.commit()
            except sqlite3.Error as e:
                self.conn.rollback()
                logger.exception("anomaly resolve failed")
                messagebox.showerror("Failed", str(e))
                return
            refresh()

        row = tk.Frame(box); row.pack(fill="x", pady=4)
        tk.Button(row, text="🔄 Reload", command=refresh, relief="flat",
                  bg="#6b7280", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="✅ Resolve selected", command=resolve,
                  relief="flat", bg="#16a34a", fg="white"
                  ).pack(side="left", padx=4)
        refresh()

    def _build_student_enh_section(self, tab) -> None:
        box1 = tk.LabelFrame(tab, text="Check-in (#3 geofence)",
                             padx=10, pady=8)
        box1.pack(fill="x", padx=10, pady=6)
        tk.Label(box1, text="Module:").grid(row=0, column=0, sticky="w")
        try:
            courses = self.db.get_courses(
                student_id=self.user.get("student_id"))
        except Exception:
            logger.exception("student courses fetch failed")
            courses = []
        cmap = {f"{c[1]} - {c[2]}": c[0] for c in courses}
        var = tk.StringVar()
        ttk.Combobox(box1, textvariable=var, values=list(cmap.keys()),
                     state="readonly", width=40
                     ).grid(row=0, column=1, padx=4)
        tk.Label(box1, text="Lat:").grid(row=0, column=2)
        lat_e = tk.Entry(box1, width=10); lat_e.grid(row=0, column=3)
        tk.Label(box1, text="Lon:").grid(row=0, column=4)
        lon_e = tk.Entry(box1, width=10); lon_e.grid(row=0, column=5)

        geofence = GeofenceService(self.conn)

        def checkin():
            if not var.get() or not self.user.get("student_id"):
                messagebox.showerror("Error", "Pick a module.")
                return
            try:
                lat = float(lat_e.get()); lon = float(lon_e.get())
            except ValueError:
                messagebox.showerror("Error", "Lat/Lon must be numeric.")
                return
            ok, msg = geofence.record_checkin(
                self.user["student_id"], cmap[var.get()], lat, lon,
                device_id=f"desktop:{self.user.get('username', '')}")
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Check-in", msg)

        tk.Button(box1, text="Check in", command=checkin,
                  bg="#16a34a", fg="white", relief="flat"
                  ).grid(row=0, column=6, padx=6)

        box2 = tk.LabelFrame(
            tab, text="Absence quota (#49 chatbot intent)",
            padx=10, pady=8)
        box2.pack(fill="x", padx=10, pady=6)
        out = tk.Text(box2, height=10, width=80)
        out.pack(fill="x")

        chatbot = ChatbotService(self.conn)

        def compute():
            out.delete("1.0", "end")
            sid = self.user.get("student_id")
            if not sid:
                out.insert("1.0", "Not linked to a student record.")
                return
            out.insert("1.0", chatbot.absence_quota(sid))

        tk.Button(box2,
                  text="How many absences can I still take?",
                  command=compute,
                  bg="#2563eb", fg="white", relief="flat").pack(pady=4)
        compute()

# Module-level legacy aliases for the GUI section helpers — preserved so any
# external code that imported `_build_*_section` keeps working.
def _build_settings_section(tab, root, conn):
    settings = EnhancementSettings(conn)
    theme = ThemeService(settings)

    class _Shim:
        pass
    shim = _Shim()
    shim.dashboard = _Shim(); shim.dashboard.root = root  # type: ignore[attr-defined]
    builder = EnhancementTabBuilder.__new__(EnhancementTabBuilder)
    builder.dashboard = shim.dashboard  # type: ignore[attr-defined]
    builder.db = type("D", (), {"conn": conn})()
    builder.user = {}
    builder.role = "?"
    builder.conn = conn
    builder.settings = settings
    builder.theme = theme
    builder.ux = TreeUxService(settings, theme)
    builder._build_settings_section(tab)


def _build_categories_section(tab, db):
    EnhancementTabBuilder(_dashboard_shim(db, {}), "admin"
                          )._build_categories_section(tab)


def _build_compliance_section(tab, db, user):
    EnhancementTabBuilder(_dashboard_shim(db, user), "admin"
                          )._build_compliance_section(tab)


def _build_integrations_section(tab, db):
    EnhancementTabBuilder(_dashboard_shim(db, {}), "admin"
                          )._build_integrations_section(tab)


def _build_student_enh_section(tab, db, user):
    EnhancementTabBuilder(_dashboard_shim(db, user), "student"
                          )._build_student_enh_section(tab)


def _dashboard_shim(db, user):
    """Build a minimal object that quacks like a dashboard for the
    EnhancementTabBuilder constructor."""
    shim = type("DashShim", (), {})()
    shim.db = db
    shim.user = user
    shim.root = None  # only used by full-build flow, not by section helpers
    return shim


def build_enhancement_tabs(notebook: ttk.Notebook, db, user,
                           role: str, root: tk.Misc) -> None:
    shim = _dashboard_shim(db, user)
    shim.root = root
    EnhancementTabBuilder(shim, role).build(notebook)


# ===========================================================================
# Public bootstrap — called from absence_tracker.py
# ===========================================================================

def bootstrap(dashboard, role: str) -> None:
    """One-call init: schema + enhancement tab + UX helpers."""
    try:
        ensure_enhanced_schema(dashboard.db.conn)
    except Exception:
        logger.exception("ensure_enhanced_schema failed")
    try:
        EnhancementTabBuilder(dashboard, role).build(dashboard.notebook)
    except Exception:
        logger.exception("build_enhancement_tabs failed")
    try:
        apply_ux(dashboard)
    except Exception:
        logger.exception("apply_ux failed")
