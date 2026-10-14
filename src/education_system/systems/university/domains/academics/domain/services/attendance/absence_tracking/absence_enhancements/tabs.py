"""Role-aware GUI sections and the public bootstrap."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .log import logger
from .schema import ensure_enhanced_schema
from .settings import EnhancementSettings
from .theme import (
    THEMES,
    ThemeService,
)
from .tree_ux import (
    TreeUxService,
    apply_ux,
)
from .checkin import GeofenceService
from .categories import RequestCategoryService
from .push import PushQueueService
from .compliance import ComplianceService
from .evidence import EvidenceService
from .lms import LmsSyncService
from .anomaly import AnomalyService
from .chatbot import ChatbotService


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


__all__ = [
    "_tree",
    "EnhancementTabBuilder",
    "_build_settings_section",
    "_build_categories_section",
    "_build_compliance_section",
    "_build_integrations_section",
    "_build_student_enh_section",
    "_dashboard_shim",
    "build_enhancement_tabs",
    "bootstrap",
]
