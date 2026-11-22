"""Batch readings: a folder of files, an LMS export, or chosen files, all
for one module (required) and optionally one assignment. Each file's
student is the student number in its file name (six or more digits);
files without one are skipped and listed. Jobs can be scheduled for a
quiet time — the daily integrity worker runs due jobs, as the person who
scheduled them, and "Run due jobs now" runs them straight away."""

import logging
import os
import threading

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)


def _module_row(self, parent, attr):
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 6))
    ttk.Label(row, text="Module").pack(side="left")
    module = common.IdPicker(row, common.modules(self), width=32)
    module.pack(side="left", padx=4)
    ttk.Label(row, text="Assignment").pack(side="left", padx=(10, 2))
    assignment = common.IdPicker(row, (), allow_blank=True, blank_label="(none)", width=30)
    assignment.pack(side="left", padx=4)
    module.bind("<<ComboboxSelected>>",
                lambda _e: assignment.set_choices(common.assignments(module.value())))
    setattr(self, attr, (module, assignment))
    return module, assignment


def create_batch_processing_section(self, parent):
    """The short form on the Advanced page: read chosen files."""
    box = ttk.LabelFrame(parent, text="Read several files", padding=10)
    box.pack(fill="x", padx=15, pady=(0, 10))
    _module_row(self, box, "_quick_batch_pickers")
    row = ttk.Frame(box)
    row.pack(fill="x")
    ttk.Button(row, text="📁 Choose files", command=self.select_batch_files).pack(side="left",
                                                                                padx=(0, 6))
    ttk.Button(row, text="⚡ Read them", command=self.process_batch).pack(side="left")


def create_batch_processing_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Batch processing", style="Title.TLabel").pack(anchor="w", padx=15,
                                                                       pady=(15, 2))
    ttk.Label(frame, wraplength=900, text=(
        "Each file's student is the student number in its file name (six or more digits); "
        "files without one are skipped.")).pack(anchor="w", padx=15)
    work = ttk.LabelFrame(frame, text="Work", padding=10)
    work.pack(fill="x", padx=15, pady=8)
    _module_row(self, work, "_batch_pickers")
    folder_row = ttk.Frame(work)
    folder_row.pack(fill="x", pady=2)
    ttk.Label(folder_row, text="Folder:").pack(side="left")
    self.batch_folder_var = tk.StringVar(value="")
    ttk.Entry(folder_row, textvariable=self.batch_folder_var, width=60).pack(side="left", padx=4)
    ttk.Button(folder_row, text="Browse…", command=self._select_batch_folder).pack(side="left")
    ttk.Button(folder_row, text="Read the folder", command=self.batch_analyze_folder).pack(
        side="left", padx=6)
    lms_row = ttk.Frame(work)
    lms_row.pack(fill="x", pady=2)
    ttk.Label(lms_row, text="LMS export:").pack(side="left")
    self.lms_type_var = tk.StringVar(value="auto")
    ttk.Combobox(lms_row, textvariable=self.lms_type_var, state="readonly", width=10,
                 values=["auto", "canvas", "blackboard", "moodle"]).pack(side="left", padx=4)
    self.lms_file_var = tk.StringVar(value="")
    ttk.Entry(lms_row, textvariable=self.lms_file_var, width=48).pack(side="left", padx=4)
    ttk.Button(lms_row, text="Browse…", command=self._select_lms_file).pack(side="left")
    ttk.Button(lms_row, text="Read the export", command=self.batch_analyze_lms_export).pack(
        side="left", padx=6)

    schedule = ttk.LabelFrame(frame, text="Schedule (runs as you)", padding=10)
    schedule.pack(fill="x", padx=15, pady=8)
    ttk.Label(schedule, text="Time").pack(side="left")
    self.schedule_hour_var = tk.StringVar(value="02")
    ttk.Spinbox(schedule, textvariable=self.schedule_hour_var, from_=0, to=23, width=4,
                format="%02.0f").pack(side="left", padx=(4, 0))
    ttk.Label(schedule, text=":").pack(side="left")
    self.schedule_min_var = tk.StringVar(value="00")
    ttk.Spinbox(schedule, textvariable=self.schedule_min_var, from_=0, to=59, width=4,
                format="%02.0f").pack(side="left")
    ttk.Button(schedule, text="Schedule the folder",
               command=lambda: self.schedule_batch_job("folder")).pack(side="left", padx=6)
    ttk.Button(schedule, text="Schedule the export",
               command=lambda: self.schedule_batch_job("lms")).pack(side="left")

    jobs = ttk.LabelFrame(frame, text="Jobs", padding=8)
    jobs.pack(fill="both", expand=True, padx=15, pady=(8, 15))
    controls = ttk.Frame(jobs)
    controls.pack(fill="x", pady=(0, 6))
    ttk.Button(controls, text="🔄 Refresh", command=self.view_batch_job_status).pack(
        side="left", padx=(0, 6))
    ttk.Button(controls, text="Cancel selected", command=self.cancel_batch_job).pack(
        side="left", padx=(0, 6))
    ttk.Button(controls, text="Retry failed", command=self.retry_failed_analyses).pack(
        side="left", padx=(0, 6))
    ttk.Button(controls, text="Run due jobs now", command=self.run_due_batch_jobs).pack(
        side="left")
    cols = (("job_id", "Job", 170), ("job_type", "Type", 60), ("course_code", "Module", 90),
            ("status", "Status", 80), ("scheduled_time", "At", 60),
            ("created_by", "By", 90), ("created_at", "Created", 140), ("error", "Error", 260))
    self.batch_job_tree = ttk.Treeview(jobs, columns=[c[0] for c in cols], show="headings",
                                       height=8)
    for col, label, width in cols:
        self.batch_job_tree.heading(col, text=label)
        self.batch_job_tree.column(col, width=width, anchor="w")
    self.batch_job_tree.pack(fill="both", expand=True)
    self._batch_job_columns = [c[0] for c in cols]
    self.view_batch_job_status()


def _picked(self, attr):
    module, assignment = self.__dict__.get(attr, (None, None))
    if module is None or not module.value():
        messagebox.showwarning(common.TITLE, "Choose the module the work belongs to.",
                               parent=self.root)
        return None
    return module.value(), assignment.value()


def _run_in_thread(self, title, fn, *args, **kwargs):
    """Run a long backend call off the main loop and show its result."""
    self.update_status(f"{title}…")
    self.show_progress(True)

    def work():
        try:
            out = fn(*args, **kwargs)
        except Exception as exc:
            logger.exception("%s failed", title)
            out = {"success": False, "error": str(exc)}
        ui(self.root, _done, self, title, out)

    start_thread(self.root, work)


def _done(self, title, out):
    self.show_progress(False)
    if common.result_failed(self, out):
        self.update_status(f"{title}: not done")
        return
    self.update_status(f"{title}: done")
    common.text_window(self, title, out, 680, 480)
    if self.__dict__.get("batch_job_tree") is not None:
        self.view_batch_job_status()


def select_batch_files(self):
    paths = filedialog.askopenfilenames(parent=self.root, title="Choose files",
                                        filetypes=[("Documents", "*.txt *.md *.pdf *.docx"),
                                                   ("All files", "*.*")])
    self.batch_files = list(paths)
    if paths:
        self.update_status(f"{len(paths)} file(s) chosen")


def process_batch(self):
    """Read the chosen files for the module (student from each file name)."""
    files = self.__dict__.get("batch_files") or []
    if not files:
        messagebox.showwarning(common.TITLE, "Choose the files first.", parent=self.root)
        return
    picked = _picked(self, "_quick_batch_pickers")
    if not picked:
        return
    module, assignment = picked
    detector = self.detector

    def run():
        out = {"read": [], "skipped": []}
        for path in files:
            name = os.path.basename(path)
            student = detector._extract_student_id_from_filename(name)
            if student == "unknown":
                out["skipped"].append(f"{name}: no student number in the name")
                continue
            try:
                text = self._extract_text_from_file(path)
                result = detector.analyze_text(text=text, title=name, student_id=student,
                                               course_code=module, assignment_id=assignment)
                out["read"].append(f"{name}: {common.summary(result)}" if not
                                   result.get("skipped") else f"{name}: {result['reason']}")
            except Exception as exc:
                out["skipped"].append(f"{name}: {exc}")
        return out

    _run_in_thread(self, "Reading the chosen files", run)


def _select_batch_folder(self):
    folder = filedialog.askdirectory(parent=self.root, title="Folder of work")
    if folder:
        self.batch_folder_var.set(folder)


def _select_lms_file(self):
    path = filedialog.askopenfilename(parent=self.root, title="LMS export",
                                      filetypes=[("Exports", "*.zip *.csv"),
                                                 ("All files", "*.*")])
    if path:
        self.lms_file_var.set(path)
        self._lms_file_path = path


def batch_analyze_folder(self):
    folder = self.batch_folder_var.get().strip()
    if not folder or not os.path.isdir(folder):
        messagebox.showwarning(common.TITLE, "Choose a folder.", parent=self.root)
        return
    picked = _picked(self, "_batch_pickers")
    if picked:
        _run_in_thread(self, "Reading the folder", self.detector.batch_analyze_folder, folder,
                       course_code=picked[0], assignment_id=picked[1])


def batch_analyze_lms_export(self):
    path = self.lms_file_var.get().strip()
    if not path or not os.path.exists(path):
        messagebox.showwarning(common.TITLE, "Choose the export file.", parent=self.root)
        return
    picked = _picked(self, "_batch_pickers")
    if picked:
        _run_in_thread(self, "Reading the LMS export", self.detector.batch_analyze_lms_export,
                       path, self.lms_type_var.get(), course_code=picked[0],
                       assignment_name=picked[1])


def schedule_batch_job(self, job_type="folder"):
    target = (self.batch_folder_var.get() if job_type == "folder" else
              self.lms_file_var.get()).strip()
    if not target:
        messagebox.showwarning(common.TITLE, "Choose the folder or export first.",
                               parent=self.root)
        return
    picked = _picked(self, "_batch_pickers")
    if not picked:
        return
    when = f"{int(self.schedule_hour_var.get()):02d}:{int(self.schedule_min_var.get()):02d}"
    out = common.call(self, self.detector.schedule_batch_job, job_type, target, when,
                      course_code=picked[0], assignment_id=picked[1])
    if out and not common.result_failed(self, out):
        self.update_status(f"Job {out.get('job_id')} scheduled for {when}")
        self.view_batch_job_status()


def view_batch_job_status(self):
    tree = self.__dict__.get("batch_job_tree")
    if tree is None or not tree.winfo_exists():
        return
    out = common.call(self, self.detector.view_batch_job_status) or {}
    if out.get("error"):
        messagebox.showerror(common.TITLE, out["error"], parent=self.root)
        return
    tree.delete(*tree.get_children())
    for job in out.get("jobs", []):
        tree.insert("", "end", iid=str(job.get("job_id")),
                    values=[job.get(c) for c in self._batch_job_columns])
    summary = out.get("summary", {})
    self.update_status("Jobs: " + ", ".join(f"{k} {v}" for k, v in summary.items()))


def cancel_batch_job(self):
    sel = self.batch_job_tree.selection()
    if not sel:
        messagebox.showwarning(common.TITLE, "Select a job.", parent=self.root)
        return
    if not messagebox.askyesno(common.TITLE, f"Cancel job {sel[0]}?", parent=self.root):
        return
    out = common.call(self, self.detector.cancel_batch_job, sel[0])
    if out and not common.result_failed(self, out):
        self.view_batch_job_status()


def retry_failed_analyses(self):
    out = common.call(self, self.detector.retry_failed_analyses)
    if out and not common.result_failed(self, out):
        self.update_status(f"{out.get('retried', 0)} failed job(s) queued again")
        self.view_batch_job_status()


def run_due_batch_jobs(self):
    """Run every queued job whose time has come, now."""
    _run_in_thread(self, "Running due jobs", self.detector.run_due_batch_jobs)


def _extract_text_from_file(self, file_path):
    """Plain text from a document (the integrity text extractor)."""
    from education_system.systems.university.infrastructure.integrity import text_extract
    return text_extract.extract(file_path)
