"""Result and job-detail dialogs for the bulk operations window.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import json
import tkinter as tk

from education_system.systems.sixth_form.domain.learners.bulk_operations.base import Job


# ══ Dialogs ═══════════════════════════════════════════════════════

class _ResultDialog:
    """Used for the 'Preview with diff' button and rich dry-run output."""

    def __init__(self, parent: tk.Misc, header: str,
                  lines: list[str]) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Bulk operation preview")
        self.win.transient(parent)
        self.win.geometry("760x520")
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=header,
                   font=("", 11, "bold")).pack(anchor="w")
        ttk.Separator(form).pack(fill="x", pady=(4, 8))
        txt = tk.Text(form, wrap="none",
                        font=("TkFixedFont", 10))
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", "\n".join(lines) if lines else
                   "(no per-target detail available)")
        txt.configure(state="disabled")
        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(
            anchor="e", pady=(8, 0))


class JobDetailDialog:
    def __init__(self, parent: tk.Misc, job: Job) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title(f"Job #{job.job_id}")
        self.win.transient(parent)
        self.win.geometry("760x600")

        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(
            form,
            text=f"#{job.job_id}  ·  {job.ran_at}  ·  {job.operation}",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            form,
            text=(f"Targets: {job.target_count}  ·  "
                   f"OK: {job.success_count}  ·  "
                   f"Fail: {job.failure_count}  ·  "
                   f"Ran by: {job.ran_by or '—'}"),
            foreground="#555",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(form, text="Summary:",
                   font=("", 10, "bold")).pack(anchor="w")
        s_t = tk.Text(form, height=3, wrap="word")
        s_t.insert("1.0", job.summary)
        s_t.configure(state="disabled")
        s_t.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Parameters:",
                   font=("", 10, "bold")).pack(anchor="w")
        p_t = tk.Text(form, height=8, wrap="none",
                         font=("TkFixedFont", 9))
        p_t.insert("1.0", json.dumps(job.parameters, indent=2)
                    if job.parameters else "(none)")
        p_t.configure(state="disabled")
        p_t.pack(fill="x", pady=(0, 8))

        nb = ttk.Notebook(form)
        nb.pack(fill="both", expand=True)

        succ_frame = ttk.Frame(nb)
        nb.add(succ_frame, text=f"Successes ({len(job.success_ids)})")
        succ_t = tk.Text(succ_frame, wrap="none",
                            font=("TkFixedFont", 9))
        succ_t.insert("1.0",
                        "\n".join(job.success_ids)
                        if job.success_ids else "(none)")
        succ_t.configure(state="disabled")
        succ_t.pack(fill="both", expand=True)

        fail_frame = ttk.Frame(nb)
        nb.add(fail_frame, text=f"Failures ({len(job.failures)})")
        fail_t = tk.Text(fail_frame, wrap="none",
                            font=("TkFixedFont", 9))
        fail_t.insert("1.0",
                        "\n".join(f"{sid}: {reason}"
                                    for sid, reason in job.failures)
                        if job.failures else "(none)")
        fail_t.configure(state="disabled")
        fail_t.pack(fill="both", expand=True)

        ttk.Button(form, text="Close",
                    command=self.win.destroy).pack(pady=(10, 0))
