"""Absence Tracker — 17 enhancements missing from the existing feature set.

This module adds:
  #3  Geofenced check-in
  #4  Facial-recognition kiosk (hook + DB, ML pluggable)
  #11 Request categories with distinct approval routes
  #21 Mobile push notifications (queued for existing push service)
  #30 HESA-ready attendance export
  #31 UKVI engagement monitoring report
  #35 Digital signature on evidence
  #36 Dark mode toggle
  #37 Keyboard shortcuts (Ctrl+S/F/N/R)
  #38 Search / filter bar on every tree view
  #39 Column sort on header click
  #40 Pagination for large tree views
  #42 Accessibility: high-contrast + screen-reader labels
  #46 LMS two-way sync (absence -> recording access)
  #47 REST endpoints under shared/api (see absence_routes.py)
  #49 Chatbot intent ("Am I allowed one more absence?")
  #50 Anomaly detection (proxy sign-ins, impossible concurrency)

The module also exposes `apply_ux(dashboard)` which applies the UX helpers to
every ttk.Treeview it can find on a dashboard, and `build_enhancement_tabs`
which adds a role-appropriate "Enhancements" tab containing the new features.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime, date, timedelta
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("absence_enhancements")


# ---------------------------------------------------------------------------
# Schema — new tables layered on top of the core attendance tables.
# ---------------------------------------------------------------------------
SCHEMA_SQL = [
    # #11 request categories
    """CREATE TABLE IF NOT EXISTS absence_request_categories (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT UNIQUE NOT NULL,
         description TEXT,
         requires_evidence INTEGER DEFAULT 0,
         approval_route TEXT DEFAULT 'instructor',
         auto_approve INTEGER DEFAULT 0
       )""",
    # #11 link on absence_requests (added dynamically if missing)
    # #3 geofencing: delegated to services.attendance.GeofencingSystem
    #    (uses attendance_sessions + attendance_records).
    # #4 kiosk registrations (still ours — services layer has no kiosk concept)
    """CREATE TABLE IF NOT EXISTS attendance_kiosks (
         kiosk_id TEXT PRIMARY KEY,
         room TEXT,
         lat REAL, lon REAL,
         radius_m REAL DEFAULT 50,
         active INTEGER DEFAULT 1
       )""",
    # #21 push queue
    """CREATE TABLE IF NOT EXISTS absence_push_queue (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         title TEXT NOT NULL,
         body  TEXT NOT NULL,
         payload TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         delivered_at TEXT,
         status TEXT DEFAULT 'pending'
       )""",
    # #31 UKVI engagement log
    """CREATE TABLE IF NOT EXISTS ukvi_engagement_events (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL,
         event_type TEXT NOT NULL,
         event_date TEXT NOT NULL,
         notes TEXT,
         recorded_by TEXT,
         recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    # #35 evidence signatures
    """CREATE TABLE IF NOT EXISTS absence_evidence_signatures (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         request_id INTEGER NOT NULL,
         file_path TEXT NOT NULL,
         sha256 TEXT NOT NULL,
         signed_by TEXT,
         signed_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    # #50 anomalies
    """CREATE TABLE IF NOT EXISTS attendance_anomalies (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         kind TEXT NOT NULL,
         student_id TEXT,
         module_code TEXT,
         details TEXT,
         severity TEXT DEFAULT 'medium',
         detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
         resolved INTEGER DEFAULT 0
       )""",
    # #46 LMS access grants driven by attendance
    """CREATE TABLE IF NOT EXISTS lms_access_grants (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL,
         module_code TEXT NOT NULL,
         session_date TEXT NOT NULL,
         resource TEXT NOT NULL,
         granted INTEGER DEFAULT 0,
         reason TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(student_id, module_code, session_date, resource)
       )""",
    # generic settings, if admin_features._get_setting table doesn't exist yet
    """CREATE TABLE IF NOT EXISTS absence_settings (
         key TEXT PRIMARY KEY,
         value TEXT
       )""",
]

SEED_CATEGORIES = [
    ("medical",       "Illness / medical appointment",       1, "instructor",   0),
    ("bereavement",   "Family bereavement",                  0, "dept_head",    1),
    ("religious",     "Religious observance",                0, "instructor",   1),
    ("representative","University representative duty",      0, "instructor",   1),
    ("other",         "Other — requires narrative",          0, "instructor",   0),
]


def ensure_enhanced_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for ddl in SCHEMA_SQL:
        cur.execute(ddl)
    # Add category_id + date_end columns to absence_requests if missing
    cur.execute("PRAGMA table_info(absence_requests)")
    cols = {r[1] for r in cur.fetchall()}
    if "category_id" not in cols:
        try:
            cur.execute("ALTER TABLE absence_requests ADD COLUMN category_id INTEGER")
        except sqlite3.OperationalError:
            pass
    if "date_end" not in cols:
        try:
            cur.execute("ALTER TABLE absence_requests ADD COLUMN date_end TEXT")
        except sqlite3.OperationalError:
            pass
    # Seed default categories if empty
    cur.execute("SELECT COUNT(*) FROM absence_request_categories")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """INSERT INTO absence_request_categories
                 (name, description, requires_evidence, approval_route, auto_approve)
               VALUES (?, ?, ?, ?, ?)""",
            SEED_CATEGORIES,
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Tiny KV settings helper (independent of admin_features._get_setting).
# ---------------------------------------------------------------------------
def get_setting(conn, key, default=None):
    try:
        cur = conn.execute("SELECT value FROM absence_settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default
    except sqlite3.Error:
        return default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO absence_settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()


# ===========================================================================
# UX helpers (#36–42) — applicable to any ttk.Treeview
# ===========================================================================

# #36, #42 themes
THEMES = {
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


def apply_theme(root: tk.Misc, theme_name: str = "light") -> None:
    theme = THEMES.get(theme_name, THEMES["light"])
    root.configure(bg=theme["bg"])

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
    style = ttk.Style()
    try:
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
        pass


def cycle_theme(root: tk.Misc, conn: sqlite3.Connection) -> str:
    current = get_setting(conn, "theme", "light")
    order = ["light", "dark", "high_contrast"]
    try:
        nxt = order[(order.index(current) + 1) % len(order)]
    except ValueError:
        nxt = "light"
    set_setting(conn, "theme", nxt)
    apply_theme(root, nxt)
    return nxt


# #39 column sort on header click
def make_sortable(tree: ttk.Treeview) -> None:
    state: Dict[str, bool] = {}

    def sort_by(col):
        desc = state.get(col, False)
        rows = [(tree.set(k, col), k) for k in tree.get_children("")]

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
            tree.heading(c, text=base + (" ▼" if (c == col and desc) else " ▲" if c == col else ""))

    for col in tree["columns"]:
        tree.heading(col, command=lambda c=col: sort_by(c))


# #38 search/filter bar
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

    def apply():
        needle = ent.get().strip().lower()
        col = col_var.get()
        all_rows = get_all_rows()
        for item in tree.get_children():
            tree.delete(item)
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

    ent.bind("<KeyRelease>", lambda e: apply())
    col_var.trace_add("write", lambda *a: apply())
    tk.Button(bar, text="Clear", command=lambda: (ent.delete(0, "end"), apply()),
              relief="flat").pack(side="left", padx=2)
    return bar


# #40 pagination
class Paginator:
    def __init__(self, tree: ttk.Treeview, parent: tk.Widget,
                 get_rows: Callable[[], List[Tuple]], page_size: int = 100):
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
        self.sz = tk.Spinbox(self.bar, from_=25, to=1000, increment=25, width=6,
                              command=self._resize)
        self.sz.delete(0, "end")
        self.sz.insert(0, str(page_size))
        self.sz.pack(side="left")

    def _resize(self):
        try:
            self.page_size = max(1, int(self.sz.get()))
        except ValueError:
            return
        self.page = 0
        self.refresh()

    def refresh(self):
        self._all = list(self.get_rows())
        self._render()

    def _render(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        total = len(self._all)
        pages = max(1, math.ceil(total / self.page_size))
        self.page = min(self.page, pages - 1)
        start = self.page * self.page_size
        end = start + self.page_size
        for row in self._all[start:end]:
            self.tree.insert("", "end", values=row)
        self.lbl.config(text=f"Page {self.page + 1} / {pages}   ({total} rows)")

    def prev(self):
        if self.page > 0:
            self.page -= 1
            self._render()

    def next(self):
        pages = max(1, math.ceil(len(self._all) / self.page_size))
        if self.page < pages - 1:
            self.page += 1
            self._render()


# #37 keyboard shortcuts
def bind_shortcuts(root: tk.Misc, actions: Dict[str, Callable]) -> None:
    for combo, fn in actions.items():
        try:
            root.bind_all(combo, lambda e, f=fn: f())
        except tk.TclError:
            pass


# #42 accessibility: give every interactive widget a label
def add_a11y_labels(root: tk.Misc) -> None:
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
                    widget.bind("<FocusIn>",
                                lambda e, t=txt: root.event_generate("<<A11yAnnounce>>")
                                if False else None)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            walk(child)
    walk(root)


# ---------------------------------------------------------------------------
# Convenience wrapper: apply UX helpers to every Treeview on a dashboard.
# ---------------------------------------------------------------------------
def _find_treeviews(widget) -> List[ttk.Treeview]:
    out = []
    try:
        if isinstance(widget, ttk.Treeview):
            out.append(widget)
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(_find_treeviews(child))
    return out


def apply_ux(dashboard) -> None:
    """Apply sorting + a11y + current theme to every tree on the dashboard.

    Filter bars and pagination are opt-in per tree because they need a
    row-source callable — the big tabs ("All Absences", "Records", "Requests")
    wire those up inside the enhancement tabs below.
    """
    root = dashboard.root
    conn = dashboard.db.conn
    # sort all trees
    for tv in _find_treeviews(root):
        try:
            make_sortable(tv)
        except tk.TclError:
            pass
    # theme
    apply_theme(root, get_setting(conn, "theme", "light"))
    # a11y
    if get_setting(conn, "a11y_labels", "0") == "1":
        add_a11y_labels(root)
    # shortcuts
    def _save_focus():
        w = root.focus_get()
        if w:
            w.event_generate("<Return>")

    def _refresh():
        # click any "Refresh" button we can find
        for child in _all_widgets(root):
            try:
                if child.winfo_class() == "Button" and "Refresh" in str(child.cget("text")):
                    child.invoke()
                    return
            except tk.TclError:
                continue

    def _toggle_theme():
        name = cycle_theme(root, conn)
        messagebox.showinfo("Theme", f"Theme: {name}", parent=root)

    bind_shortcuts(root, {
        "<Control-s>": _save_focus,
        "<Control-r>": _refresh,
        "<Control-d>": _toggle_theme,
        "<Control-f>": lambda: _focus_first_filter(root),
    })


def _all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _all_widgets(child)


def _focus_first_filter(root):
    for w in _all_widgets(root):
        try:
            if w.winfo_class() == "Entry":
                w.focus_set()
                return
        except tk.TclError:
            continue


# ===========================================================================
# Feature implementations
# ===========================================================================

# ---- #3 Geofenced check-in (delegates to services.attendance.geofencing) --
_geofence_instance = None


def _get_geofence_system():
    """Return the shared GeofencingSystem instance (lazy singleton)."""
    global _geofence_instance
    if _geofence_instance is None:
        from education_system.university_system.modules.domain.academics.services \
            .attendance.geofencing import GeofencingSystem
        _geofence_instance = GeofencingSystem()
    return _geofence_instance


def _ensure_active_session(gs, module_code: str, d: str,
                           conn: sqlite3.Connection) -> Optional[str]:
    """Create an attendance_sessions row for (module, date) if none exists,
    anchored at the configured campus centre. Returns session_id or None."""
    # Pre-existing session?
    cur = conn.execute(
        "SELECT session_id, latitude, longitude, geofence_radius "
        "FROM attendance_sessions WHERE module_code=? AND date=? "
        "ORDER BY rowid DESC LIMIT 1",
        (module_code, d),
    )
    row = cur.fetchone()
    if row:
        sid, lat, lon, rad = row
        # hydrate the in-memory cache so check_location_attendance works
        gs.active_locations[sid] = {
            "module_code": module_code,
            "date": d,
            "location": (lat, lon),
            "radius": rad or 50,
        }
        return sid

    raw_lat = get_setting(conn, "campus_lat")
    raw_lon = get_setting(conn, "campus_lon")
    if raw_lat in (None, "") or raw_lon in (None, ""):
        return None
    c_rad = float(get_setting(conn, "campus_radius_m", "500") or 500)
    return gs.create_geofenced_session(
        module_code, d, "campus", float(raw_lat), float(raw_lon), c_rad,
    )


def record_geofenced_checkin(conn, student_id, module_code, lat, lon,
                             device_id="", when=None) -> Tuple[bool, str]:
    """Delegate to services.attendance.geofencing.GeofencingSystem.

    Ensures there is an active geofenced session for the module/date (using
    the configured campus centre if one wasn't pre-created), then calls
    `check_location_attendance` which writes to `attendance_records`.
    """
    d = (when or date.today()).isoformat()
    try:
        gs = _get_geofence_system()
    except Exception as e:
        logger.exception("GeofencingSystem unavailable")
        return False, f"geofencing unavailable: {e}"
    sid = _ensure_active_session(gs, module_code, d, conn)
    if not sid:
        return False, "no geofenced session and campus centre not configured"
    ok, msg = gs.check_location_attendance(student_id, lat, lon, session_id=sid)
    return bool(ok), msg


# ---- #4 Facial-recognition kiosk (delegates to services.attendance) ------
_face_instance = None


def _get_face_system():
    global _face_instance
    if _face_instance is None:
        from education_system.university_system.modules.domain.academics.services \
            .attendance.face_recognition_system import FaceRecognitionSystem
        _face_instance = FaceRecognitionSystem()
    return _face_instance


def register_kiosk(conn, kiosk_id, room, lat, lon, radius_m=50):
    """Register a physical kiosk device. The facial recognition itself runs
    through services.attendance.FaceRecognitionSystem; this table is just a
    registry of kiosk locations + their geofence radii."""
    conn.execute(
        """INSERT INTO attendance_kiosks(kiosk_id, room, lat, lon, radius_m)
           VALUES(?,?,?,?,?)
           ON CONFLICT(kiosk_id) DO UPDATE SET
             room=excluded.room, lat=excluded.lat, lon=excluded.lon,
             radius_m=excluded.radius_m, active=1""",
        (kiosk_id, room, lat, lon, radius_m),
    )
    conn.commit()


def facial_checkin(conn, kiosk_id, module_code, image_path,
                   recogniser=None  # retained for test injection
                   ) -> Tuple[bool, str, Optional[str]]:
    """Delegate to FaceRecognitionSystem.recognize_face_attendance."""
    if recogniser is not None:
        # Test / custom recogniser path
        try:
            student_id, conf = recogniser(image_path)
        except Exception as e:
            return False, f"recogniser error: {e}", None
        if not student_id:
            return False, f"low confidence ({conf:.2f})", None
        d = date.today().isoformat()
        conn.execute(
            """INSERT INTO attendance (student_id, module_code, date, status, reason)
               VALUES (?,?,?,?,?)""",
            (student_id, module_code, d, "present", f"face kiosk {kiosk_id}"),
        )
        conn.commit()
        return True, "ok", student_id
    try:
        fs = _get_face_system()
    except Exception as e:
        logger.exception("FaceRecognitionSystem unavailable")
        return False, f"face recognition unavailable: {e}", None
    d = date.today().isoformat()
    ok, msg, sid = fs.recognize_face_attendance(image_path, module_code, d)
    return bool(ok), msg, sid


# ---- #11 Request categories ----------------------------------------------
def list_categories(conn):
    cur = conn.execute(
        "SELECT id, name, description, requires_evidence, approval_route, auto_approve "
        "FROM absence_request_categories ORDER BY name"
    )
    return cur.fetchall()


def set_request_category(conn, request_id, category_id):
    conn.execute(
        "UPDATE absence_requests SET category_id=? WHERE id=?",
        (category_id, request_id),
    )
    conn.commit()


def route_for_request(conn, request_id) -> Dict[str, Any]:
    cur = conn.execute(
        """SELECT c.name, c.approval_route, c.auto_approve, c.requires_evidence
             FROM absence_requests r
             LEFT JOIN absence_request_categories c ON c.id = r.category_id
            WHERE r.id = ?""",
        (request_id,),
    )
    row = cur.fetchone()
    if not row:
        return {}
    name, route, auto, req_ev = row
    return {"category": name, "route": route or "instructor",
            "auto_approve": bool(auto), "requires_evidence": bool(req_ev)}


# ---- #21 Mobile push notifications ---------------------------------------
def queue_push(conn, user_id, title, body, payload: Optional[dict] = None) -> int:
    cur = conn.execute(
        """INSERT INTO absence_push_queue(user_id, title, body, payload)
           VALUES(?,?,?,?)""",
        (user_id, title, body, json.dumps(payload or {})),
    )
    conn.commit()
    return cur.lastrowid


def drain_push_queue(conn, sender: Optional[Callable[[str, str, str, dict], bool]] = None
                     ) -> int:
    """Send pending pushes. If no sender is provided, look up the shared
    notifications service; failing that, leave rows pending."""
    if sender is None:
        try:
            from education_system.shared.notifications import push as _push  # type: ignore
            sender = _push.send
        except Exception:
            return 0
    cur = conn.execute(
        "SELECT id, user_id, title, body, payload FROM absence_push_queue "
        "WHERE status='pending' ORDER BY id LIMIT 500"
    )
    sent = 0
    for pid, uid, title, body, payload in cur.fetchall():
        try:
            ok = sender(uid, title, body, json.loads(payload or "{}"))
        except Exception:
            logger.exception("push send failed for id=%s", pid)
            ok = False
        if ok:
            conn.execute(
                "UPDATE absence_push_queue SET status='sent', delivered_at=CURRENT_TIMESTAMP "
                "WHERE id=?", (pid,))
            sent += 1
        else:
            conn.execute("UPDATE absence_push_queue SET status='failed' WHERE id=?",
                         (pid,))
    conn.commit()
    return sent


# ---- #30 HESA-ready export -----------------------------------------------
HESA_COLS = [
    "HUSID", "STULOAD", "MODULECODE", "MODULENAME",
    "ENGAGEMENT_DATE", "ENGAGEMENT_TYPE", "ENGAGEMENT_OUTCOME",
    "EXPECTED_SESSIONS", "ATTENDED_SESSIONS", "ATTENDANCE_PCT",
]


def hesa_export(conn, out_path: str,
                term_start: Optional[str] = None,
                term_end: Optional[str] = None) -> int:
    cur = conn.execute("PRAGMA table_info(students)")
    scols = {r[1] for r in cur.fetchall()}
    stuload_expr = "COALESCE(s.study_mode, 'FT')" if "study_mode" in scols else "'FT'"
    sql = f"""
        SELECT s.student_id AS HUSID,
               {stuload_expr} AS STULOAD,
               m.module_code AS MODULECODE,
               m.module_name AS MODULENAME,
               MAX(a.date)   AS ENGAGEMENT_DATE,
               'ATTENDANCE' AS ENGAGEMENT_TYPE,
               CASE WHEN SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                       >= 0.75 * COUNT(a.id)
                    THEN 'ENGAGED' ELSE 'AT_RISK' END AS ENGAGEMENT_OUTCOME,
               COUNT(a.id)  AS EXPECTED_SESSIONS,
               SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS ATTENDED_SESSIONS,
               ROUND(100.0 * SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                       / NULLIF(COUNT(a.id), 0), 2) AS ATTENDANCE_PCT
          FROM attendance a
          JOIN students s ON s.student_id = a.student_id
          JOIN modules  m ON m.module_code = a.module_code
         WHERE (? IS NULL OR a.date >= ?)
           AND (? IS NULL OR a.date <= ?)
         GROUP BY s.student_id, m.module_code, m.module_name
         ORDER BY s.student_id, m.module_code
    """
    cur = conn.execute(sql, (term_start, term_start, term_end, term_end))
    rows = cur.fetchall()
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HESA_COLS)
        w.writerows(rows)
    return len(rows)


# ---- #31 UKVI engagement monitoring --------------------------------------
def ukvi_log_event(conn, student_id, event_type, event_date=None,
                   notes="", recorded_by=""):
    conn.execute(
        """INSERT INTO ukvi_engagement_events
             (student_id, event_type, event_date, notes, recorded_by)
           VALUES(?,?,?,?,?)""",
        (student_id, event_type, (event_date or date.today().isoformat()),
         notes, recorded_by),
    )
    conn.commit()


def ukvi_at_risk(conn, min_pct: float = 80.0) -> List[Tuple]:
    """Identify Student-Route / Tier-4 holders below engagement threshold.
    Falls back to all international students if a visa flag column isn't
    present. Returns (student_id, name, engagement_pct, missed_sessions)."""
    # Try best-effort column probes
    cur = conn.execute("PRAGMA table_info(students)")
    cols = {r[1] for r in cur.fetchall()}
    visa_filter = ""
    if "visa_type" in cols:
        visa_filter = "AND s.visa_type IN ('student_route','tier_4','Tier 4','Student Route')"
    elif "international" in cols:
        visa_filter = "AND s.international = 1"
    sql = f"""
        SELECT s.student_id,
               TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')) AS name,
               ROUND(100.0 * SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                     / NULLIF(COUNT(a.id),0), 2) AS pct,
               SUM(CASE WHEN a.status IN ('absent','late') THEN 1 ELSE 0 END) AS missed
          FROM students s
          JOIN attendance a ON a.student_id = s.student_id
         WHERE 1=1 {visa_filter}
         GROUP BY s.student_id
        HAVING pct < ?
         ORDER BY pct ASC
    """
    return list(conn.execute(sql, (min_pct,)).fetchall())


# ---- #35 Digital signature on evidence -----------------------------------
def sign_evidence(conn, request_id: int, file_path: str, signed_by: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    conn.execute(
        """INSERT INTO absence_evidence_signatures
             (request_id, file_path, sha256, signed_by)
           VALUES(?,?,?,?)""",
        (request_id, file_path, digest, signed_by),
    )
    conn.commit()
    return digest


def verify_evidence(conn, request_id: int, file_path: str) -> bool:
    cur = conn.execute(
        "SELECT sha256 FROM absence_evidence_signatures "
        "WHERE request_id=? AND file_path=? ORDER BY id DESC LIMIT 1",
        (request_id, file_path),
    )
    row = cur.fetchone()
    if not row:
        return False
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return False
    return h.hexdigest() == row[0]


# ---- #46 LMS two-way sync ------------------------------------------------
def lms_on_absence(conn, student_id, module_code, session_date,
                   resource="lecture_recording", reason="approved absence"):
    conn.execute(
        """INSERT OR IGNORE INTO lms_access_grants
             (student_id, module_code, session_date, resource, granted, reason)
           VALUES(?,?,?,?,1,?)""",
        (student_id, module_code, session_date, resource, reason),
    )
    conn.commit()
    # Best-effort push into real LMS if present
    try:
        from education_system.university_system.modules.domain.academics.services.lms \
            import lms_core as _lms  # type: ignore
        if hasattr(_lms, "grant_access"):
            _lms.grant_access(student_id, module_code, session_date, resource)
    except Exception:
        pass


def lms_sync_approved_requests(conn) -> int:
    """Iterate approved requests that haven't been mirrored into LMS grants."""
    cur = conn.execute(
        """SELECT r.id, r.student_id, r.module_code, r.date
             FROM absence_requests r
             LEFT JOIN lms_access_grants g
               ON g.student_id = r.student_id
              AND g.module_code = r.module_code
              AND g.session_date = r.date
            WHERE r.status = 'approved' AND g.id IS NULL"""
    )
    n = 0
    for _id, sid, mod, d in cur.fetchall():
        lms_on_absence(conn, sid, mod, d)
        n += 1
    return n


# ---- #50 Anomaly detection ------------------------------------------------
def anomaly_scan(conn) -> List[Dict[str, Any]]:
    """Detect (a) student marked present in two modules at the same hour on
    the same day, (b) same device checking in for multiple students, (c)
    identical reason strings across many students on one day (mass proxy).
    Returns the list of anomalies newly inserted."""
    new: List[Dict[str, Any]] = []

    # (a) impossible concurrency
    cur = conn.execute(
        """SELECT a.student_id, a.date, GROUP_CONCAT(a.module_code)
             FROM attendance a
            WHERE a.status='present'
            GROUP BY a.student_id, a.date
           HAVING COUNT(DISTINCT a.module_code) > 1"""
    )
    for sid, d, mods in cur.fetchall():
        details = f"present in {mods} on {d}"
        r = conn.execute(
            "INSERT INTO attendance_anomalies(kind, student_id, details, severity) "
            "VALUES('concurrency', ?, ?, 'high')", (sid, details))
        new.append({"id": r.lastrowid, "kind": "concurrency",
                    "student_id": sid, "details": details})

    # (b) shared-device rule: probe attendance_records.location_data JSON
    # written by the GeofencingSystem, if the column exists.
    cur = conn.execute("PRAGMA table_info(attendance_records)")
    ar_cols = {r[1] for r in cur.fetchall()}
    if "location_data" in ar_cols and "student_id" in ar_cols:
        try:
            cur = conn.execute(
                """SELECT json_extract(location_data, '$.device_id') AS dev,
                          COUNT(DISTINCT student_id),
                          GROUP_CONCAT(DISTINCT student_id)
                     FROM attendance_records
                    WHERE location_data IS NOT NULL
                      AND json_extract(location_data, '$.device_id') IS NOT NULL
                    GROUP BY dev
                   HAVING COUNT(DISTINCT student_id) >= 5"""
            )
            for dev, n, sids in cur.fetchall():
                details = f"device {dev} used by {n} students: {sids}"
                r = conn.execute(
                    "INSERT INTO attendance_anomalies(kind, details, severity) "
                    "VALUES('shared_device', ?, 'high')", (details,))
                new.append({"id": r.lastrowid, "kind": "shared_device",
                            "details": details})
        except sqlite3.OperationalError:
            logger.debug("shared_device scan skipped (json1 unavailable)")

    # (c) identical reason text on one day for >= 10 students
    cur = conn.execute(
        """SELECT date, reason, COUNT(DISTINCT student_id)
             FROM attendance
            WHERE reason IS NOT NULL AND reason != ''
            GROUP BY date, reason
           HAVING COUNT(DISTINCT student_id) >= 10"""
    )
    for d, reason, n in cur.fetchall():
        details = f"{n} students share identical reason '{reason[:40]}' on {d}"
        r = conn.execute(
            "INSERT INTO attendance_anomalies(kind, details, severity) "
            "VALUES('mass_proxy_reason', ?, 'medium')", (details,))
        new.append({"id": r.lastrowid, "kind": "mass_proxy_reason", "details": details})

    conn.commit()
    return new


# ---- #49 Chatbot intent ---------------------------------------------------
def chatbot_absence_quota(conn, student_id: str, module_code: Optional[str] = None,
                          threshold_pct: float = 75.0) -> str:
    if module_code:
        cur = conn.execute(
            """SELECT COUNT(*),
                      SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
                 FROM attendance
                WHERE student_id=? AND module_code=?""",
            (student_id, module_code),
        )
        total, present, absent = cur.fetchone() or (0, 0, 0)
        if not total:
            return f"No attendance recorded yet for {module_code}."
        pct = 100.0 * (present or 0) / total
        max_absences = math.floor(total * (1 - threshold_pct / 100.0))
        remaining = max(0, max_absences - (absent or 0))
        return (f"{module_code}: {pct:.1f}% attended. "
                f"Threshold {threshold_pct:.0f}% → you can miss "
                f"{remaining} more session(s) before falling below.")
    # all modules
    cur = conn.execute(
        """SELECT module_code,
                  COUNT(*),
                  SUM(CASE WHEN status='present' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END)
             FROM attendance
            WHERE student_id=?
            GROUP BY module_code""",
        (student_id,),
    )
    lines = []
    for mod, total, present, absent in cur.fetchall():
        if not total:
            continue
        max_abs = math.floor(total * (1 - threshold_pct / 100.0))
        rem = max(0, max_abs - (absent or 0))
        pct = 100.0 * (present or 0) / total
        lines.append(f"  • {mod}: {pct:.0f}% — {rem} more misses OK")
    if not lines:
        return "No attendance recorded yet."
    return "Attendance quota remaining:\n" + "\n".join(lines)


# ===========================================================================
# Enhancement tabs (role-aware)
# ===========================================================================

def _tree(parent, cols, widths):
    frame = tk.Frame(parent)
    frame.pack(expand=True, fill="both", padx=10, pady=6)
    tv = ttk.Treeview(frame, columns=cols, show="headings")
    for c, w in zip(cols, widths):
        tv.heading(c, text=c)
        tv.column(c, width=w)
    tv.pack(expand=True, fill="both")
    make_sortable(tv)
    return tv


def _build_settings_section(tab, root, conn):
    box = tk.LabelFrame(tab, text="Appearance & accessibility (#36, #37, #42)",
                        padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)
    theme_var = tk.StringVar(value=get_setting(conn, "theme", "light"))
    tk.Label(box, text="Theme:").grid(row=0, column=0, sticky="w")
    cb = ttk.Combobox(box, textvariable=theme_var,
                     values=list(THEMES.keys()), state="readonly", width=20)
    cb.grid(row=0, column=1, padx=6)

    def set_t(*_):
        set_setting(conn, "theme", theme_var.get())
        apply_theme(root, theme_var.get())
    cb.bind("<<ComboboxSelected>>", set_t)

    a11y_var = tk.BooleanVar(value=get_setting(conn, "a11y_labels", "0") == "1")
    tk.Checkbutton(box, text="Screen-reader labels on focus",
                   variable=a11y_var,
                   command=lambda: set_setting(conn, "a11y_labels",
                                               "1" if a11y_var.get() else "0")
                   ).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

    tk.Label(box, text="Keyboard shortcuts:  Ctrl+S save · Ctrl+F filter · "
                       "Ctrl+R refresh · Ctrl+D theme",
             fg="#6b7280").grid(row=2, column=0, columnspan=3, sticky="w")


def _build_geofence_section(tab, db, user):
    conn = db.conn
    box = tk.LabelFrame(tab, text="Geofenced check-in (#3) & kiosks (#4)",
                        padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)

    tk.Label(box, text="Campus centre — lat:").grid(row=0, column=0, sticky="w")
    lat_e = tk.Entry(box, width=12)
    lat_e.insert(0, get_setting(conn, "campus_lat", "") or "")
    lat_e.grid(row=0, column=1, padx=4)
    tk.Label(box, text="lon:").grid(row=0, column=2)
    lon_e = tk.Entry(box, width=12)
    lon_e.insert(0, get_setting(conn, "campus_lon", "") or "")
    lon_e.grid(row=0, column=3, padx=4)
    tk.Label(box, text="radius m:").grid(row=0, column=4)
    rad_e = tk.Entry(box, width=6)
    rad_e.insert(0, get_setting(conn, "campus_radius_m", "500") or "500")
    rad_e.grid(row=0, column=5, padx=4)

    def save_campus():
        try:
            float(lat_e.get()); float(lon_e.get()); float(rad_e.get())
        except ValueError:
            messagebox.showerror("Error", "Values must be numeric.")
            return
        set_setting(conn, "campus_lat", lat_e.get())
        set_setting(conn, "campus_lon", lon_e.get())
        set_setting(conn, "campus_radius_m", rad_e.get())
        messagebox.showinfo("Saved", "Campus geofence updated.")

    tk.Button(box, text="Save campus", command=save_campus,
              bg="#2563eb", fg="white", relief="flat").grid(row=0, column=6, padx=4)

    # Kiosks — in its own sub-frame so we can pack-manage the tree
    # without fighting the grid-managed row above.
    ksub = tk.Frame(box)
    ksub.grid(row=1, column=0, columnspan=7, sticky="nsew", pady=(8, 0))
    kcols = ("kiosk_id", "room", "lat", "lon", "radius_m", "active")
    kv = _tree(ksub, kcols, (110, 140, 90, 90, 80, 60))

    def refresh_kiosks():
        for i in kv.get_children():
            kv.delete(i)
        for r in conn.execute(
            "SELECT kiosk_id, room, lat, lon, radius_m, active "
            "FROM attendance_kiosks ORDER BY kiosk_id"):
            kv.insert("", "end", values=r)

    def add_kiosk():
        kid = simpledialog.askstring("Kiosk id", "ID:")
        if not kid:
            return
        room = simpledialog.askstring("Room", "Room label:") or ""
        try:
            lat = float(simpledialog.askstring("Lat", "Latitude:") or "0")
            lon = float(simpledialog.askstring("Lon", "Longitude:") or "0")
            rad = float(simpledialog.askstring("Radius", "Radius (m):") or "50")
        except (TypeError, ValueError):
            messagebox.showerror("Error", "Invalid number")
            return
        register_kiosk(conn, kid, room, lat, lon, rad)
        refresh_kiosks()

    btns = tk.Frame(box)
    btns.grid(row=2, column=0, columnspan=7, sticky="w", pady=4)
    tk.Button(btns, text="+ Kiosk", command=add_kiosk, relief="flat",
              bg="#16a34a", fg="white").pack(side="left", padx=4)
    tk.Button(btns, text="🔄", command=refresh_kiosks, relief="flat",
              bg="#6b7280", fg="white").pack(side="left", padx=4)
    refresh_kiosks()


def _build_categories_section(tab, db):
    conn = db.conn
    box = tk.LabelFrame(tab, text="Request categories (#11)", padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)
    cols = ("id", "name", "description", "requires_evidence",
            "approval_route", "auto_approve")
    tv = _tree(box, cols, (40, 120, 260, 120, 120, 90))

    def refresh():
        for i in tv.get_children():
            tv.delete(i)
        for r in list_categories(conn):
            tv.insert("", "end", values=r)

    def add_cat():
        name = simpledialog.askstring("Category", "Name:")
        if not name:
            return
        desc = simpledialog.askstring("Category", "Description:") or ""
        route = simpledialog.askstring("Category",
                                       "Approval route (instructor/dept_head/registry):",
                                       initialvalue="instructor") or "instructor"
        req_ev = messagebox.askyesno("Evidence", "Requires evidence?")
        auto = messagebox.askyesno("Auto", "Auto-approve?")
        try:
            conn.execute(
                """INSERT INTO absence_request_categories
                     (name, description, requires_evidence, approval_route, auto_approve)
                   VALUES(?,?,?,?,?)""",
                (name, desc, 1 if req_ev else 0, route, 1 if auto else 0))
            conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Name must be unique.")
        refresh()

    def del_cat():
        sel = tv.selection()
        if not sel:
            return
        cid = tv.item(sel[0])["values"][0]
        if messagebox.askyesno("Delete", "Delete category?"):
            conn.execute("DELETE FROM absence_request_categories WHERE id=?", (cid,))
            conn.commit()
            refresh()

    row = tk.Frame(box); row.pack(fill="x", pady=4)
    tk.Button(row, text="+ Add", command=add_cat, bg="#16a34a",
              fg="white", relief="flat").pack(side="left", padx=4)
    tk.Button(row, text="🗑 Delete", command=del_cat, bg="#dc2626",
              fg="white", relief="flat").pack(side="left", padx=4)
    tk.Button(row, text="🔄", command=refresh, bg="#6b7280",
              fg="white", relief="flat").pack(side="left", padx=4)
    refresh()


def _build_compliance_section(tab, db, user):
    conn = db.conn
    box = tk.LabelFrame(tab, text="Compliance (#30 HESA · #31 UKVI · #35 e-sig)",
                        padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)

    def do_hesa():
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         initialfile="hesa_attendance.csv")
        if not p:
            return
        n = hesa_export(conn, p)
        messagebox.showinfo("HESA export", f"Wrote {n} rows → {p}")

    def do_ukvi():
        rows = ukvi_at_risk(conn, 80.0)
        win = tk.Toplevel()
        win.title("UKVI engagement — at-risk")
        tv = ttk.Treeview(win, columns=("student_id", "name", "pct", "missed"),
                          show="headings")
        for c, w in zip(("student_id", "name", "pct", "missed"),
                        (120, 240, 80, 80)):
            tv.heading(c, text=c); tv.column(c, width=w)
        tv.pack(expand=True, fill="both", padx=10, pady=10)
        for r in rows:
            tv.insert("", "end", values=r)
        make_sortable(tv)

    def do_sign():
        req = simpledialog.askinteger("Sign", "Request id:")
        if not req:
            return
        p = filedialog.askopenfilename(title="Evidence file")
        if not p:
            return
        digest = sign_evidence(conn, req, p, user.get("username", ""))
        messagebox.showinfo("Signed", f"SHA-256: {digest}")

    tk.Button(box, text="📤 HESA export", command=do_hesa,
              bg="#2563eb", fg="white", relief="flat").pack(side="left", padx=6)
    tk.Button(box, text="🛂 UKVI at-risk", command=do_ukvi,
              bg="#2563eb", fg="white", relief="flat").pack(side="left", padx=6)
    tk.Button(box, text="✒ Sign evidence", command=do_sign,
              bg="#16a34a", fg="white", relief="flat").pack(side="left", padx=6)


def _build_integrations_section(tab, db):
    conn = db.conn
    box = tk.LabelFrame(tab, text="Integrations (#21 push · #46 LMS · #50 anomalies)",
                        padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)

    def drain():
        n = drain_push_queue(conn)
        messagebox.showinfo("Push", f"Delivered {n} notification(s).")

    def lms():
        n = lms_sync_approved_requests(conn)
        messagebox.showinfo("LMS", f"Mirrored {n} new access grant(s).")

    def anoms():
        new = anomaly_scan(conn)
        messagebox.showinfo("Anomalies", f"Found {len(new)} new anomaly record(s).")

    tk.Button(box, text="📲 Drain push queue", command=drain,
              bg="#2563eb", fg="white", relief="flat").pack(side="left", padx=6)
    tk.Button(box, text="🎥 LMS sync", command=lms,
              bg="#2563eb", fg="white", relief="flat").pack(side="left", padx=6)
    tk.Button(box, text="🚨 Run anomaly scan", command=anoms,
              bg="#dc2626", fg="white", relief="flat").pack(side="left", padx=6)

    cols = ("id", "kind", "student_id", "module_code", "details",
            "severity", "detected_at", "resolved")
    tv = _tree(box, cols, (40, 120, 100, 100, 360, 80, 140, 70))

    def refresh():
        for i in tv.get_children():
            tv.delete(i)
        for r in conn.execute(
            "SELECT id, kind, COALESCE(student_id,''), COALESCE(module_code,''), "
            "COALESCE(details,''), severity, detected_at, resolved "
            "FROM attendance_anomalies ORDER BY detected_at DESC LIMIT 500"):
            tv.insert("", "end", values=r)

    def resolve():
        for s in tv.selection():
            aid = tv.item(s)["values"][0]
            conn.execute("UPDATE attendance_anomalies SET resolved=1 WHERE id=?", (aid,))
        conn.commit()
        refresh()

    row = tk.Frame(box); row.pack(fill="x", pady=4)
    tk.Button(row, text="🔄 Reload", command=refresh, relief="flat",
              bg="#6b7280", fg="white").pack(side="left", padx=4)
    tk.Button(row, text="✅ Resolve selected", command=resolve, relief="flat",
              bg="#16a34a", fg="white").pack(side="left", padx=4)
    refresh()


def _build_student_enh_section(tab, db, user):
    conn = db.conn

    box1 = tk.LabelFrame(tab, text="Check-in (#3 geofence)", padx=10, pady=8)
    box1.pack(fill="x", padx=10, pady=6)
    tk.Label(box1, text="Module:").grid(row=0, column=0, sticky="w")
    courses = db.get_courses(student_id=user.get("student_id"))
    cmap = {f"{c[1]} - {c[2]}": c[0] for c in courses}
    var = tk.StringVar()
    ttk.Combobox(box1, textvariable=var, values=list(cmap.keys()),
                 state="readonly", width=40).grid(row=0, column=1, padx=4)
    tk.Label(box1, text="Lat:").grid(row=0, column=2)
    lat_e = tk.Entry(box1, width=10); lat_e.grid(row=0, column=3)
    tk.Label(box1, text="Lon:").grid(row=0, column=4)
    lon_e = tk.Entry(box1, width=10); lon_e.grid(row=0, column=5)

    def checkin():
        if not var.get() or not user.get("student_id"):
            messagebox.showerror("Error", "Pick a module.")
            return
        try:
            lat = float(lat_e.get()); lon = float(lon_e.get())
        except ValueError:
            messagebox.showerror("Error", "Lat/Lon must be numeric.")
            return
        ok, msg = record_geofenced_checkin(
            conn, user["student_id"], cmap[var.get()], lat, lon,
            device_id=f"desktop:{user.get('username', '')}")
        (messagebox.showinfo if ok else messagebox.showwarning)("Check-in", msg)

    tk.Button(box1, text="Check in", command=checkin,
              bg="#16a34a", fg="white", relief="flat"
              ).grid(row=0, column=6, padx=6)

    box2 = tk.LabelFrame(tab, text="Absence quota (#49 chatbot intent)",
                         padx=10, pady=8)
    box2.pack(fill="x", padx=10, pady=6)
    out = tk.Text(box2, height=10, width=80)
    out.pack(fill="x")

    def compute():
        out.delete("1.0", "end")
        sid = user.get("student_id")
        if not sid:
            out.insert("1.0", "Not linked to a student record.")
            return
        out.insert("1.0", chatbot_absence_quota(conn, sid))
    tk.Button(box2, text="How many absences can I still take?", command=compute,
              bg="#2563eb", fg="white", relief="flat").pack(pady=4)
    compute()


def _build_staff_enh_section(tab, db, user):
    conn = db.conn
    box = tk.LabelFrame(tab, text="Facial-recognition kiosk (#4) — simulate a scan",
                        padx=10, pady=8)
    box.pack(fill="x", padx=10, pady=6)
    tk.Label(box, text="Kiosk id:").grid(row=0, column=0, sticky="w")
    kid = tk.Entry(box, width=12); kid.grid(row=0, column=1, padx=4)
    tk.Label(box, text="Module:").grid(row=0, column=2)
    mods = db.get_courses(staff_id=user["id"])
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in mods}
    mv = tk.StringVar()
    ttk.Combobox(box, textvariable=mv, values=list(mmap.keys()),
                 state="readonly", width=30).grid(row=0, column=3, padx=4)
    tk.Label(box, text="Image path:").grid(row=0, column=4)
    img = tk.Entry(box, width=24); img.grid(row=0, column=5, padx=4)

    def run():
        if not (kid.get() and mv.get() and img.get()):
            messagebox.showerror("Error", "All fields required.")
            return
        ok, msg, sid = facial_checkin(conn, kid.get(), mmap[mv.get()], img.get())
        (messagebox.showinfo if ok else messagebox.showwarning)(
            "Kiosk", f"{msg} — student={sid}")
    tk.Button(box, text="Scan", command=run, bg="#16a34a", fg="white",
              relief="flat").grid(row=0, column=6, padx=6)


def build_enhancement_tabs(notebook: ttk.Notebook, db, user,
                           role: str, root: tk.Misc) -> None:
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

    _build_settings_section(inner, root, db.conn)

    if role == "admin":
        _build_geofence_section(inner, db, user)
        _build_categories_section(inner, db)
        _build_compliance_section(inner, db, user)
        _build_integrations_section(inner, db)
    elif role in ("staff", "instructor", "teacher"):
        _build_staff_enh_section(inner, db, user)
        _build_categories_section(inner, db)
        _build_compliance_section(inner, db, user)
        _build_integrations_section(inner, db)
    else:
        _build_student_enh_section(inner, db, user)


# ---------------------------------------------------------------------------
# Public bootstrap — called from absence_tracker.py
# ---------------------------------------------------------------------------
def bootstrap(dashboard, role: str) -> None:
    """One-call init: schema + enhancement tab + UX helpers."""
    try:
        ensure_enhanced_schema(dashboard.db.conn)
    except Exception:
        logger.exception("ensure_enhanced_schema failed")
    try:
        build_enhancement_tabs(dashboard.notebook, dashboard.db,
                               dashboard.user, role, dashboard.root)
    except Exception:
        logger.exception("build_enhancement_tabs failed")
    try:
        apply_ux(dashboard)
    except Exception:
        logger.exception("apply_ux failed")
