"""Database Report section.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class DatabaseReportMixin:
    # ------------------------------------------------------------------
    # Section: Database Report (full PDF extract of every DB file)
    # ------------------------------------------------------------------

    def _open_path(self, path):
        """Open a file with the OS default application.

        Returns True if a handler launched successfully, False otherwise (e.g.
        no PDF viewer is registered on a headless Linux box — xdg-open then
        prints "No applications found for mimetype").
        """
        import sys
        import subprocess
        try:
            if sys.platform.startswith("darwin"):
                return subprocess.call(["open", path]) == 0
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
                return True
            # Linux: xdg-open exits non-zero when no handler is registered.
            return subprocess.call(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        except Exception:
            return False

    def _build_db_report(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Database Report",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Extract every database in the education system into a single PDF "
                 "report with summary charts, table inventories and sample data.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 14))

        # Discover databases and show what will be included.
        try:
            from education_system.platform.delivery.gui.db_report import (
                discover_databases, generate_database_report,
            )
            db_paths = discover_databases()
        except Exception as exc:
            tk.Label(
                frame, text=f"Report module unavailable: {exc}",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg="#c0392b",
            ).pack(anchor=tk.W, padx=24)
            return

        card = tk.Frame(frame, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(0, 14))
        tk.Label(
            card, text=f"{len(db_paths)} database file(s) found:",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 2))
        for p in db_paths:
            try:
                size_kb = os.path.getsize(p) / 1024
            except OSError:
                size_kb = 0
            tk.Label(
                card, text=f"   •  {p.name}  ({size_kb:,.0f} KB)",
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED, anchor=tk.W,
            ).pack(anchor=tk.W, padx=12)
        tk.Frame(card, bg=CARD_BG, height=8).pack()

        # Options row.
        opts = tk.Frame(frame, bg=CONTENT_BG)
        opts.pack(fill=tk.X, padx=24, pady=(0, 8))
        tk.Label(
            opts, text="Max sample rows per table:",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT)
        rows_var = tk.StringVar(value="50")
        tk.Entry(opts, textvariable=rows_var, font=("Segoe UI", 10), width=6).pack(side=tk.LEFT, padx=6)

        # Progress + status.
        progress_var = tk.DoubleVar(value=0)
        status_var = tk.StringVar(value="Ready.")
        bar = ttk.Progressbar(frame, variable=progress_var, maximum=100, length=420)
        bar.pack(anchor=tk.W, padx=24, pady=(8, 2))
        tk.Label(
            frame, textvariable=status_var,
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24)

        state = {"running": False}

        from education_system.platform.delivery.gui.tk_threads import ui

        def _on_progress(frac, msg):
            # Called from the worker thread — marshal onto the Tk main loop.
            ui(self, lambda: (progress_var.set(frac * 100), status_var.set(msg)))

        def _done(result, err):
            state["running"] = False
            gen_btn.config(state=tk.NORMAL)
            if err is not None:
                status_var.set("Failed.")
                messagebox.showerror("Report failed", str(err))
                return
            progress_var.set(100)
            score = result.get("data_quality_score")
            issues = result.get("issues")
            extra = f" · quality {score}% · {issues} issue(s)" if score is not None else ""
            status_var.set(
                f"Done — {result['databases']} databases, {result['rows']:,} rows{extra}.")
            saved_at = result["output_path"]
            summary = (f"{result['databases']} databases · {result['rows']:,} rows · "
                       f"data-quality score {score}% ({issues} issues found)\n\n"
                       if score is not None else "\n")
            if messagebox.askyesno(
                "Report ready",
                f"Report saved to:\n{saved_at}\n\n{summary}Open it now?",
            ):
                if not self._open_path(saved_at):
                    # No PDF handler available (common on headless Linux).
                    messagebox.showinfo(
                        "Report saved",
                        "Couldn't find an application to open PDFs on this system.\n\n"
                        f"The report is saved here:\n{saved_at}")

        def _worker(path, max_rows):
            try:
                result = generate_database_report(
                    path, max_rows_per_table=max_rows, progress_cb=_on_progress)
                ui(self, _done, result, None)
            except Exception as exc:  # noqa: BLE001 — surface any failure to the user
                ui(self, _done, None, exc)

        def _generate():
            if state["running"]:
                return
            from tkinter import filedialog
            default_name = f"edu_db_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            path = filedialog.asksaveasfilename(
                title="Save Database Report",
                defaultextension=".pdf",
                initialfile=default_name,
                filetypes=[("PDF document", "*.pdf")],
            )
            if not path:
                return
            try:
                max_rows = max(1, int(rows_var.get()))
            except (ValueError, TypeError):
                max_rows = 50
            state["running"] = True
            gen_btn.config(state=tk.DISABLED)
            progress_var.set(0)
            status_var.set("Starting…")
            from education_system.platform.delivery.gui.tk_threads import start_thread
            start_thread(self, _worker, path, max_rows)

        gen_btn = tk.Button(
            frame, text="Generate PDF Report", font=("Segoe UI", 11, "bold"),
            bg="#1abc9c", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2",
            padx=16, pady=8, command=_generate,
        )
        gen_btn.pack(anchor=tk.W, padx=24, pady=(12, 20))
