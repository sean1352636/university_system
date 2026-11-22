"""Shared helpers for the AI Content Detector window: the analysis pickers,
e-mailing a reading to yourself, system monitoring (real figures: readings,
the processing queue, components that did not start, the database, recent
audit-chain events), reports, and the older notebook-tab entry points."""

import json
import logging
import os
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


# ── analysis pickers ────────────────────────────────────────────────────


def _load_database_data(self):
    """Fill the analysis pickers: modules the person reviews (by module
    code); students and assignments follow the chosen module."""
    self.module_combo.set_choices(common.modules(self))
    self.student_combo.set_choices(())
    self.assignment_combo.set_choices(())


def _on_module_selected(self, event=None):
    """Students on the chosen module and its assignments (real ids)."""
    module_code = self.module_combo.value()
    if not module_code:
        return
    self.student_combo.set_choices(common.students(module_code))
    self.assignment_combo.set_choices(common.assignments(module_code))


# ── e-mailing a reading to yourself ─────────────────────────────────────


def _reading_mail(self, analysis_results):
    lines = [f"AI-writing reading {analysis_results.get('result_id')}",
             f"Student: {analysis_results.get('student_id')}",
             f"Module: {analysis_results.get('course_code')}",
             f"Reading: {common.summary(analysis_results)}", ""]
    for i in analysis_results.get("indicators") or []:
        lines.append(f"- {i.get('label')}: {i.get('shown')} — {i.get('meaning')}")
    lines += ["", common.NOTICE]
    return "AI-writing reading", "\n".join(lines)


def _send_email_via_gui(self, to_email, subject, message):
    """Queue an e-mail through the university outbox."""
    from education_system.systems.university.infrastructure.ui.record_screens import send_emails
    return send_emails([(to_email, subject, message)]) > 0


def _show_ai_detection_email_fallback(self, email, subject, message, analysis_results):
    common.text_window(self, f"Not sent — copy it to {email or 'yourself'}",
                       f"Subject: {subject}\n\n{message}", 700, 500)


def auto_send_ai_report_on_completion(self, analysis_results):
    """E-mail the reading to the signed-in member of staff."""
    email = (self.user or {}).get("email")
    if email:
        self.send_ai_detection_report_via_email(analysis_results, email)


def send_ai_detection_report_via_email(self, analysis_results, user_email=None):
    """E-mail a reading (indicators and notice, never the student's text)."""
    email = user_email or (self.user or {}).get("email")
    subject, message = _reading_mail(self, analysis_results)
    if email and self._send_email_via_gui(email, subject, message):
        messagebox.showinfo(common.TITLE, f"Sent to {email}", parent=self.root)
    else:
        self._show_ai_detection_email_fallback(email, subject, message, analysis_results)


# ── health checks ───────────────────────────────────────────────────────


def check_api_health(self):
    gateway = getattr(self.detector, "api_gateway", None)
    if gateway is None:
        return {"status": False, "details": self.detector.component_errors.get(
            "api_gateway", "not started")}
    return {"status": True, "details": f"{len(getattr(gateway, 'api_configs', {}) or {})} "
                                       "external API(s) configured"}


def check_database_health(self):
    try:
        conn = self.detector._safe_db_connect()
        try:
            readings = conn.execute("SELECT COUNT(*) FROM ai_detector_results").fetchone()[0]
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            conn.close()
        return {"status": quick == "ok", "details": f"{readings} reading(s); integrity {quick}"}
    except Exception as exc:
        return {"status": False, "details": str(exc)}


def check_filesystem_health(self):
    from education_system.paths import UNIVERSITY_EXPORTS_DIR
    try:
        UNIVERSITY_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        probe = UNIVERSITY_EXPORTS_DIR / ".ai_detector_write_check"
        probe.write_text("ok", encoding="utf-8")
        ok = probe.read_text(encoding="utf-8") == "ok"
        probe.unlink()
        return {"status": ok, "details": f"exports folder writable: {UNIVERSITY_EXPORTS_DIR}"}
    except OSError as exc:
        return {"status": False, "details": str(exc)}


def check_memory_health(self):
    try:
        import psutil
    except ImportError:
        return {"status": True, "details": "psutil not installed; memory not measured"}
    memory = psutil.virtual_memory()
    return {"status": memory.percent < 90, "details": f"{memory.percent:.1f}% memory used"}


def check_model_health(self):
    version = common.call(self, self.detector.get_model_version, quiet=True)
    errors = self.detector.component_errors
    return {"status": not errors,
            "details": f"active model: {version or 'none'}; components not started: "
                       f"{', '.join(errors) or 'none'}"}


def collect_performance_data(self):
    """Real figures from the database and the processor."""
    data = {"timestamp": datetime.now().isoformat(), "db_path": self.detector.db_path}
    try:
        conn = self.detector._safe_db_connect()
        try:
            day = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            data["readings_total"] = conn.execute(
                "SELECT COUNT(*) FROM ai_detector_results").fetchone()[0]
            data["readings_last_24h"] = conn.execute(
                "SELECT COUNT(*) FROM ai_detector_results WHERE created_at >= ?",
                (day,)).fetchone()[0]
            data["readings_last_7_days"] = conn.execute(
                "SELECT COUNT(*) FROM ai_detector_results WHERE created_at >= ?",
                (week,)).fetchone()[0]
            data["alerts_waiting"] = conn.execute(
                "SELECT COUNT(*) FROM ai_detector_alerts WHERE status = 'pending'").fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        data["database_error"] = str(exc)
    processor = getattr(self.detector, "realtime_processor", None)
    if processor is not None:
        try:
            status = processor.get_status()
            data["queue"] = {k: status.get(k) for k in ("running", "waiting", "processing",
                                                        "done", "failed", "done_last_hour",
                                                        "seconds_per_item")}
        except Exception as exc:
            data["queue"] = {"error": str(exc)}
    data["components_not_started"] = dict(self.detector.component_errors)
    try:
        data["db_size_mb"] = round(os.path.getsize(self.detector.db_path) / (1024 * 1024), 1)
    except OSError:
        data["db_size_mb"] = None
    return data


def format_performance_report(self, data):
    return "SYSTEM REPORT — AI Content Detector\n" + "=" * 40 + "\n" + common.format_value(data)


# ── system monitoring ───────────────────────────────────────────────────


def create_system_monitoring_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="System monitoring", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                        pady=(15, 6))
    figures = ttk.LabelFrame(frame, text="Figures", padding=10)
    figures.pack(fill="x", padx=15, pady=6)
    self.cpu_usage_label = ttk.Label(figures, text="Readings: —")
    self.cpu_usage_label.pack(anchor="w")
    self.memory_usage_label = ttk.Label(figures, text="Queue: —")
    self.memory_usage_label.pack(anchor="w")
    self.db_size_label = ttk.Label(figures, text="Database: —")
    self.db_size_label.pack(anchor="w")
    self.analysis_speed_label = ttk.Label(figures, text="Processing time: —")
    self.analysis_speed_label.pack(anchor="w")
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", padx=15)
    ttk.Button(buttons, text="🔄 Refresh", command=self.refresh_system_metrics).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="🏥 Health check", command=self.run_system_health_check).pack(
        side="left", padx=(0, 6))
    ttk.Button(buttons, text="📊 Report", command=self.generate_performance_report).pack(
        side="left")
    problems = ttk.LabelFrame(frame, text="Problems and recent events", padding=8)
    problems.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    self.error_log_display = scrolledtext.ScrolledText(problems, height=12, wrap="word")
    self.error_log_display.pack(fill="both", expand=True)
    self.start_system_monitoring()


def refresh_system_metrics(self):
    label = self.__dict__.get("cpu_usage_label")
    if label is None or not label.winfo_exists():
        return
    data = self.collect_performance_data()
    label.config(text=f"Readings: {data.get('readings_total', '—')} in all, "
                      f"{data.get('readings_last_24h', '—')} in the last 24 h, "
                      f"{data.get('readings_last_7_days', '—')} in 7 days; "
                      f"{data.get('alerts_waiting', '—')} alert(s) waiting")
    queue = data.get("queue") or {}
    self.memory_usage_label.config(
        text=f"Queue: {'running' if queue.get('running') else 'stopped'}, "
             f"{queue.get('waiting', '—')} waiting, {queue.get('failed', '—')} failed, "
             f"{queue.get('done_last_hour', '—')} done in the last hour")
    self.db_size_label.config(text=f"Database: {data.get('db_size_mb', '—')} MB")
    speed = queue.get("seconds_per_item")
    self.analysis_speed_label.config(
        text="Processing time: " + (f"{speed:.2f} s per queued item (last hour)"
                                    if speed is not None else "no queued items in the last hour"))


def run_system_health_check(self):
    lines = []
    for name, check in (("Database", self.check_database_health),
                        ("Exports folder", self.check_filesystem_health),
                        ("Memory", self.check_memory_health),
                        ("Model and components", self.check_model_health),
                        ("External APIs", self.check_api_health)):
        try:
            result = check()
        except Exception as exc:
            result = {"status": False, "details": str(exc)}
        lines.append(f"{'✅' if result['status'] else '❌'} {name}: {result.get('details')}")
    common.text_window(self, "Health check", "\n".join(lines), 640, 360)


def generate_performance_report(self):
    common.text_window(self, "System report",
                       self.format_performance_report(self.collect_performance_data()), 700, 560)


def start_system_monitoring(self):
    """Refresh every 30 s while the view is open."""
    label = self.__dict__.get("cpu_usage_label")
    if label is None or not label.winfo_exists():
        return
    self.refresh_system_metrics()
    self.update_error_log()
    self.root.after(30000, self.start_system_monitoring)


def update_error_log(self):
    widget = self.__dict__.get("error_log_display")
    if widget is None or not widget.winfo_exists():
        return
    lines = []
    for name, error in self.detector.component_errors.items():
        lines.append(f"Component {name} did not start: {error}")
    processor = getattr(self.detector, "realtime_processor", None)
    if processor is not None:
        try:
            for f in processor.get_status().get("recent_failures", []):
                lines.append(f"Queue item {f['id']} failed at {f['at']}: {f['error']}")
        except Exception as exc:
            lines.append(f"Queue status unavailable: {exc}")
    jobs = common.call(self, self.detector.view_batch_job_status, quiet=True) or {}
    for job in jobs.get("jobs", []):
        if job.get("status") == "failed":
            lines.append(f"Batch job {job.get('job_id')} failed: {job.get('error')}")
    lines.append("")
    lines.append("Recent audit-chain events:")
    for b in self.get_audit_log_data()[:20]:
        lines.append(f"  {b['timestamp']}  {b['event']}  ({b['actor']})")
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", "\n".join(lines) if lines else "No problems recorded.")
    widget.configure(state="disabled")


def show_db_status(self):
    stats = common.call(self, self.detector.get_enhanced_statistics) or {}
    common.text_window(self, "Database status", {
        "database": self.detector.db_path, "readings you can see": stats.get("total_submissions"),
        "students": stats.get("unique_students"), "waiting for review": stats.get("needs_review"),
        "review level": stats.get("detection_threshold")}, 560, 320)


# ── reports ─────────────────────────────────────────────────────────────


def gather_analytics_data(self):
    """Counts by module and level over the readings the person may see."""
    data = common.call(self, self.detector.get_submission_history, limit=100000, quiet=True)
    if data is None:
        return {"error": "Readings could not be read"}
    by_module: dict = {}
    for s in data.get("submissions", []):
        module = by_module.setdefault(s.get("course_code") or "—", {})
        level = s.get("level") or "taken before indicators"
        module[level] = module.get(level, 0) + 1
    return {"by_module": by_module, "readings": len(data.get("submissions", []))}


def generate_comprehensive_report(self):
    try:
        return {"report_date": datetime.now().isoformat(),
                "statistics": self.detector.get_enhanced_statistics(),
                "submission_history": self.detector.get_submission_history(limit=1000),
                "notice": common.NOTICE}
    except (PermissionError, ValueError) as exc:
        return {"error": str(exc)}


def get_audit_log_data(self):
    """The audit chain's blocks, newest first."""
    chain = getattr(self.detector, "blockchain_audit", None)
    if chain is None:
        return []
    try:
        return chain.get_blocks(1000)
    except Exception as exc:
        logger.warning("Audit chain read failed: %s", exc)
        return []


# ── older notebook-tab entry points ─────────────────────────────────────


def _tab(self, label, builder):
    notebook = self.__dict__.get("notebook")
    if notebook is None:
        return None
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=label)
    builder(frame)
    return frame


def create_api_integration_tab(self):
    return _tab(self, "🔌 API", self.create_api_integration_view)


def create_bias_detection_tab(self):
    return _tab(self, "⚖️ Bias", self.create_bias_detection_view)


def create_compliance_tab(self):
    return _tab(self, "🔒 Compliance", self.create_compliance_view)


def create_data_export_import_tab(self):
    return _tab(self, "💾 Data", self.create_data_export_import_view)


def create_federated_learning_tab(self):
    return _tab(self, "🤝 Federated", self.create_federated_learning_view)


def create_predictive_analytics_tab(self):
    return _tab(self, "🔮 Predictive", self.create_predictive_analytics_view)


def create_statistics_tab(self):
    return _tab(self, "📊 Statistics", self.create_statistics_view)


def create_student_self_check_tab(self):
    return _tab(self, "✅ Self-check", self.create_student_self_check_view)


def create_system_monitoring_tab(self):
    return _tab(self, "🖥 System", self.create_system_monitoring_view)


def create_visual_analysis_tab(self):
    return _tab(self, "📸 Visual", self.create_visual_analysis_view)


def create_real_time_monitoring_tab(self):
    return _tab(self, "📡 Real-time", self.create_real_time_monitoring_view)


def patch_gui_with_missing_functions():
    """Kept for older callers: every view is bound by ``main`` already."""
    return None


def add_gui_support():
    """Give ``AIDetector`` a ``launch_gui(auth)`` that opens this window as
    the signed-in member of staff."""
    from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector.main import (
        GUILauncher,
    )
    from education_system.systems.university.shared.ai.ai_detector.detector import (
        AIDetector,
    )

    def launch_gui(detector, auth=None):
        return GUILauncher.launch_gui(detector_instance=detector,
                                      auth=auth or getattr(detector, "auth", None))

    AIDetector.launch_gui = launch_gui


def main():
    """Show the detector's statistics (needs a signed-in member of staff)."""
    from education_system.systems.university.shared.ai.ai_detector.detector import (
        AIDetector,
    )
    detector = AIDetector()
    print(json.dumps({"components_not_started": detector.component_errors}, indent=2))


def main_gui():
    """Open the window; it refuses to open without a signed-in member of staff."""
    import sys
    from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector.main import (
        GUILauncher,
    )
    GUILauncher.launch_gui(fullscreen="--fullscreen" in sys.argv[1:])
