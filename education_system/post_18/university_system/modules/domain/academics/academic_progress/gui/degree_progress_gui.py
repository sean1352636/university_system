"""Degree Progress Tracker GUI (Feature 35).

Displays a visual progress bar, summary statistics, and a colour-coded
requirements checklist for the currently logged-in student.
"""

import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.post_18.university_system.modules.shared.services.dashboard.student_services import StudentDashboardService

logger = logging.getLogger(__name__)


class DegreeProgressGUI:
    """Toplevel window showing degree progress for a student."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        # Holds the most recently loaded summary dict so it can be exported.
        self._last_summary: dict | None = None
        # Current progress percentage; cached so canvas-bar resizes redraw.
        self._progress_pct = 0.0

        self.window = tk.Toplevel(parent)
        self.window.title("Degree Progress Tracker")
        self.window.geometry("900x720")
        self.window.transient(parent)

        self._setup_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the degree progress layout."""
        ttk.Label(
            self.window,
            text="Degree Progress Tracker",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # ---- Progress bar section (custom canvas with threshold colours) ----
        progress_frame = ttk.Frame(self.window)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)

        self.progress_canvas = tk.Canvas(
            progress_frame, height=36, bg='#ecf0f1', highlightthickness=0,
        )
        self.progress_canvas.pack(fill=tk.X)
        self.progress_canvas.bind(
            '<Configure>',
            lambda _e: self._draw_progress_bar(self.progress_canvas, self._progress_pct),
        )

        # ---- Stat cards: two rows × three cards = six metrics ----
        cards_frame = ttk.Frame(self.window)
        cards_frame.pack(fill=tk.X, padx=20, pady=5)

        self.credits_var = tk.StringVar(value="--/--")
        self.gpa_var = tk.StringVar(value="--")
        self.grad_var = tk.StringVar(value="--")
        self.completed_var = tk.StringVar(value="0")
        self.in_progress_var = tk.StringVar(value="0")
        self.planned_var = tk.StringVar(value="0")

        self._create_stat_card(cards_frame, "Credits", self.credits_var, 0, 0)
        self._create_stat_card(cards_frame, "GPA", self.gpa_var, 0, 1)
        self._create_stat_card(cards_frame, "Est. Graduation", self.grad_var, 0, 2)
        self._create_stat_card(cards_frame, "Modules Completed", self.completed_var, 1, 0)
        self._create_stat_card(cards_frame, "Modules In Progress", self.in_progress_var, 1, 1)
        self._create_stat_card(cards_frame, "Modules Planned", self.planned_var, 1, 2)

        for c in range(3):
            cards_frame.columnconfigure(c, weight=1)

        # ---- UK classification banner (hidden until computed) ----
        self.classification_var = tk.StringVar(value="")
        self.classification_label = ttk.Label(
            self.window,
            textvariable=self.classification_var,
            font=('Arial', 12, 'bold'),
            anchor='center',
        )
        # Pack later in `_load_data` if a classification is computable.

        # ---- Requirements checklist ----
        req_frame = ttk.LabelFrame(self.window, text="Requirements Checklist", padding="5")
        req_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 10))

        cols = (
            'requirement_name', 'type', 'status',
            'credits_needed', 'credits_completed',
        )
        self.tree = ttk.Treeview(req_frame, columns=cols, show='headings', height=14)
        self.tree.heading('requirement_name', text='Requirement')
        self.tree.heading('type', text='Type')
        self.tree.heading('status', text='Status')
        self.tree.heading('credits_needed', text='Credits Needed')
        self.tree.heading('credits_completed', text='Credits Completed')

        self.tree.column('requirement_name', width=250)
        self.tree.column('type', width=120, anchor='center')
        self.tree.column('status', width=120, anchor='center')
        self.tree.column('credits_needed', width=120, anchor='center')
        self.tree.column('credits_completed', width=140, anchor='center')

        # Color tags for status
        self.tree.tag_configure('completed', background='#d4edda')      # green
        self.tree.tag_configure('in_progress', background='#fff3cd')    # yellow
        self.tree.tag_configure('not_started', background='#e2e3e5')    # gray

        tree_scroll = ttk.Scrollbar(req_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Status bar + Export button ----
        footer = ttk.Frame(self.window)
        footer.pack(fill=tk.X, padx=20, pady=(0, 8))

        self.status_var = tk.StringVar(value="Loading...")
        ttk.Label(footer, textvariable=self.status_var).pack(side=tk.LEFT)

        ttk.Button(
            footer, text="Export as JSON…", command=self._export_progress,
        ).pack(side=tk.RIGHT)

    def _create_stat_card(self, parent, title, text_var, row, column):
        """Create a small titled stat card widget inside a grid."""
        card = ttk.LabelFrame(parent, text=title, padding=10)
        card.grid(row=row, column=column, padx=10, pady=5, sticky='nsew')
        ttk.Label(
            card,
            textvariable=text_var,
            font=('TkDefaultFont', 14, 'bold'),
            anchor='center',
        ).pack(fill=tk.X, expand=True)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        """Load degree progress from database / service."""
        if not self.student_id:
            self.status_var.set("No student logged in.")
            return

        try:
            # Try requirement_completion table first
            requirements = self._load_requirements_from_db()

            # Get summary from service (covers credits, GPA, progress_pct)
            summary = StudentDashboardService.get_degree_progress_summary(self.student_id)
            self._last_summary = summary

            # Populate progress bar
            pct = summary.get('progress_pct', 0.0) or 0.0
            self._progress_pct = pct
            self._draw_progress_bar(self.progress_canvas, pct)

            # Populate stat cards
            earned = summary.get('credits_earned', 0)
            required = summary.get('credits_required', 120)
            self.credits_var.set(f"{earned} / {required}")

            gpa = summary.get('gpa')
            self.gpa_var.set(f"{gpa:.2f}" if isinstance(gpa, (int, float)) else "N/A")

            grad = summary.get('estimated_graduation')
            self.grad_var.set(str(grad) if grad else "--")

            # Populate requirements tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Fall back to service data if no direct DB rows
            if not requirements:
                requirements = summary.get('requirements', [])

            # Status counts for the second row of stat cards
            counts = {'completed': 0, 'in_progress': 0, 'not_started': 0}
            for req in requirements:
                name = req.get('requirement_name', '')
                rtype = req.get('requirement_type', req.get('type', ''))
                status = req.get('status', 'not_started')
                needed = req.get('credits_needed', '')
                completed = req.get('credits_completed', '')

                tag = self._status_tag(status)
                counts[tag] = counts.get(tag, 0) + 1
                self.tree.insert('', tk.END, values=(
                    name, rtype, status, needed, completed,
                ), tags=(tag,))

            self.completed_var.set(str(counts['completed']))
            self.in_progress_var.set(str(counts['in_progress']))
            self.planned_var.set(str(counts['not_started']))

            # Classification banner (only when a percentage average is available)
            average_pct = self._extract_average_percentage(summary)
            if average_pct is not None:
                cls = self._get_classification(average_pct)
                self.classification_var.set(
                    f"Current Average: {average_pct:.1f}%  →  {cls}"
                )
                # Pack the banner just above the requirements frame so it is
                # visible on every load.  pack_forget()/pack() makes the call
                # idempotent across reloads.
                self.classification_label.pack_forget()
                self.classification_label.pack(
                    fill=tk.X, padx=20, pady=(0, 5),
                    before=self.tree.master.master,
                )
            else:
                self.classification_var.set("")
                self.classification_label.pack_forget()

            count = len(requirements)
            if count == 0 and pct == 0.0 and gpa is None:
                self.status_var.set(
                    "No degree progress data found. "
                    "Your degree progress may not yet be configured."
                )
            else:
                self.status_var.set(f"Loaded {count} requirement(s).")

        except Exception as e:
            logger.error(f"Error loading degree progress: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror(
                "Error", f"Failed to load degree progress: {e}", parent=self.window
            )

    def _load_requirements_from_db(self):
        """Attempt to load requirement_completion rows directly.

        Joins with degree_requirements to get human-readable names.
        Also tries a numeric student_id since student_degree_progress
        may store '5' instead of 'S12345'.
        """
        requirements = []
        try:
            numeric_id = ''.join(c for c in self.student_id if c.isdigit())
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT dr.requirement_name, dr.requirement_type, "
                    "rc.is_completed, dr.credits_required AS credits_needed, "
                    "rc.credits_earned AS credits_completed "
                    "FROM requirement_completion rc "
                    "JOIN degree_requirements dr ON rc.requirement_id = dr.requirement_id "
                    "WHERE rc.student_id = ? OR rc.student_id = ? "
                    "ORDER BY dr.requirement_type, dr.requirement_name",
                    (self.student_id, numeric_id),
                ).fetchall()
                if rows:
                    for r in rows:
                        req_dict = dict(r)
                        req_dict['status'] = (
                            'completed' if req_dict.get('is_completed')
                            else 'in_progress'
                        )
                        requirements.append(req_dict)
        except Exception:
            # Table may not exist; that is fine, we fall back to the service.
            pass
        return requirements

    # ------------------------------------------------------------------
    # Visual helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _draw_progress_bar(canvas, pct, height=36):
        """Draw a coloured progress bar onto *canvas* sized to its current width.

        Threshold palette: red < 25 %, orange < 50 %, yellow < 75 %, green ≥ 75 %.
        """
        canvas.delete('all')
        w = canvas.winfo_width()
        # Width is 1 before the canvas has been mapped; defer the draw.
        if w <= 1:
            canvas.after(50, lambda: DegreeProgressGUI._draw_progress_bar(canvas, pct, height))
            return
        pct = max(0.0, min(100.0, float(pct)))
        fill_w = (pct / 100.0) * w

        # Background track
        canvas.create_rectangle(0, 0, w, height, fill='#ecf0f1', outline='')

        if pct >= 75:
            colour = '#27ae60'   # green
        elif pct >= 50:
            colour = '#f39c12'   # amber
        elif pct >= 25:
            colour = '#e67e22'   # orange
        else:
            colour = '#e74c3c'   # red

        canvas.create_rectangle(0, 0, fill_w, height, fill=colour, outline='')
        canvas.create_text(
            w / 2, height / 2, text=f"{pct:.1f}% Complete",
            font=('Arial', 11, 'bold'), fill='#2c3e50',
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_average_percentage(summary):
        """Best-effort lookup for an average mark percentage in *summary*.

        The dashboard service may expose this under a few different keys
        depending on degree-programme metadata; try the common ones and
        return ``None`` when nothing usable is present.
        """
        for key in ('average_percentage', 'average_grade', 'average', 'mean_grade'):
            val = summary.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        return None

    @staticmethod
    def _get_classification(avg):
        """Map an average percentage to a UK degree classification string."""
        if avg >= 70:
            return "First Class Honours (1st)"
        if avg >= 60:
            return "Upper Second Class (2:1)"
        if avg >= 50:
            return "Lower Second Class (2:2)"
        if avg >= 40:
            return "Third Class Honours (3rd)"
        return "Below Pass Mark"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_progress(self):
        """Export the loaded summary dict to a user-chosen JSON file."""
        if not self._last_summary:
            messagebox.showinfo(
                "Nothing to export",
                "Degree progress has not been loaded yet.",
                parent=self.window,
            )
            return

        path = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"degree_progress_{self.student_id or 'student'}.json",
            title="Export degree progress",
        )
        if not path:
            return

        try:
            payload = {
                'student_id': self.student_id,
                'summary': self._last_summary,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=str)
            self.status_var.set(f"Exported to {path}")
            try:
                log_activity(
                    self.student_id, 'degree_progress_export',
                    f"Exported progress to {path}",
                )
            except Exception:
                pass  # activity logger is best-effort
        except Exception as e:
            logger.exception("Failed to export degree progress")
            messagebox.showerror(
                "Export failed", f"Could not write file: {e}", parent=self.window,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_tag(status):
        """Map a status string to a treeview tag name."""
        status_lower = (status or '').lower().replace(' ', '_')
        if status_lower in ('completed', 'complete'):
            return 'completed'
        elif status_lower in ('in_progress', 'in progress', 'enrolled'):
            return 'in_progress'
        return 'not_started'
