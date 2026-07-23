"""Embedded student dashboard widgets (Features 31-43)."""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


def create_grades_summary_widget(parent, student_id):
    """Create a mini per-module grades summary table."""
    frame = ttk.LabelFrame(parent, text="Grades Summary", padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    try:
        from education_system.post_18.university_system.modules.shared.services.dashboard.student_services import (
            StudentDashboardService,
        )

        modules = StudentDashboardService.get_grades_by_module(student_id)

        if modules:
            cols = ("module", "avg_score", "letter")
            tree = ttk.Treeview(
                frame, columns=cols, show="headings",
                height=min(5, len(modules)),
            )
            tree.heading("module", text="Module")
            tree.heading("avg_score", text="Average")
            tree.heading("letter", text="Grade")
            tree.column("module", width=200)
            tree.column("avg_score", width=80)
            tree.column("letter", width=60)

            for m in modules:
                avg = m.get("average_score")
                if avg is not None:
                    if avg >= 90:
                        letter = "A"
                    elif avg >= 80:
                        letter = "B"
                    elif avg >= 70:
                        letter = "C"
                    elif avg >= 60:
                        letter = "D"
                    else:
                        letter = "F"
                    avg_text = f"{avg:.1f}"
                else:
                    letter = "N/A"
                    avg_text = "N/A"
                tree.insert("", tk.END, values=(
                    m.get("module_code", ""),
                    avg_text,
                    letter,
                ))
            tree.pack(fill=tk.X)
        else:
            ttk.Label(frame, text="No graded assignments yet.").pack(anchor="w")
    except Exception as e:
        logger.error(f"Error creating grades summary widget: {e}")
        ttk.Label(frame, text="Unable to load grades summary.").pack(anchor="w")

    return frame


def create_degree_progress_widget(parent, student_id):
    """Create a progress bar and stat cards for degree progress."""
    frame = ttk.LabelFrame(parent, text="Degree Progress", padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    try:
        from education_system.post_18.university_system.modules.shared.services.dashboard.student_services import (
            StudentDashboardService,
        )

        data = StudentDashboardService.get_degree_progress_summary(student_id)

        # Progress bar
        bar_frame = ttk.Frame(frame)
        bar_frame.pack(fill=tk.X, pady=(0, 5))
        pct = min(data["progress_pct"], 100)
        ttk.Label(bar_frame, text=f"{pct:.0f}%").pack(side=tk.RIGHT, padx=(5, 0))
        progress = ttk.Progressbar(bar_frame, length=300, mode="determinate", value=pct)
        progress.pack(fill=tk.X, expand=True)

        # Stat row
        stats_frame = ttk.Frame(frame)
        stats_frame.pack(fill=tk.X)
        ttk.Label(
            stats_frame,
            text=f"Credits: {data['credits_earned']}/{data['credits_required']}",
        ).pack(side=tk.LEFT, padx=(0, 20))
        gpa_text = f"{data['gpa']:.2f}" if data["gpa"] is not None else "N/A"
        ttk.Label(stats_frame, text=f"GPA: {gpa_text}").pack(side=tk.LEFT, padx=(0, 20))
        if data["estimated_graduation"]:
            ttk.Label(
                stats_frame, text=f"Est. Graduation: {data['estimated_graduation']}"
            ).pack(side=tk.LEFT)

    except Exception as e:
        logger.error(f"Error creating degree progress widget: {e}")
        ttk.Label(frame, text="Unable to load degree progress.").pack(anchor="w")

    return frame


def create_gpa_whatif_widget(parent, student_id, launch_callback=None):
    """Create current GPA display with 'Open Calculator' link."""
    frame = ttk.LabelFrame(parent, text="GPA What-If", padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT AVG(CASE "
                "  WHEN s.grade >= 90 THEN 4.0 "
                "  WHEN s.grade >= 80 THEN 3.0 "
                "  WHEN s.grade >= 70 THEN 2.0 "
                "  WHEN s.grade >= 60 THEN 1.0 "
                "  ELSE 0.0 END) as gpa "
                "FROM assignment_submissions s "
                "WHERE s.student_id = ? AND s.grade IS NOT NULL",
                (student_id,),
            ).fetchone()
            gpa = round(row["gpa"], 2) if row and row["gpa"] is not None else None

        gpa_text = f"{gpa:.2f}" if gpa is not None else "N/A"
        ttk.Label(frame, text=f"Current GPA: {gpa_text}",
                  font=("Arial", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Use the GPA Calculator to see how future grades affect your GPA."
                  ).pack(anchor="w", pady=(2, 5))

        if launch_callback:
            ttk.Button(frame, text="Open GPA Calculator",
                       command=launch_callback).pack(anchor="w")

    except Exception as e:
        logger.error(f"Error creating GPA what-if widget: {e}")
        ttk.Label(frame, text="Unable to load GPA info.").pack(anchor="w")

    return frame


def create_payment_alerts_widget(parent, student_id):
    """Create upcoming/overdue payment deadline alerts."""
    frame = ttk.LabelFrame(parent, text="Payment Alerts", padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    try:
        from education_system.post_18.university_system.modules.shared.services.dashboard.student_services import (
            StudentDashboardService,
        )

        data = StudentDashboardService.get_financial_summary(student_id)

        overdue = data.get("overdue_payments", [])
        upcoming = data.get("upcoming_payments", [])

        if overdue:
            ttk.Label(frame, text="Overdue:", font=("Arial", 10, "bold"),
                      foreground="red").pack(anchor="w")
            for p in overdue:
                ttk.Label(
                    frame,
                    text=f"  {p.get('description', 'Payment')} - "
                         f"£{p.get('amount', 0):.2f} (due {p.get('due_date', 'N/A')})",
                    foreground="red",
                ).pack(anchor="w")

        if upcoming:
            ttk.Label(frame, text="Upcoming:", font=("Arial", 10, "bold")).pack(
                anchor="w", pady=(5 if overdue else 0, 0)
            )
            for p in upcoming:
                ttk.Label(
                    frame,
                    text=f"  {p.get('description', 'Payment')} - "
                         f"£{p.get('amount', 0):.2f} (due {p.get('due_date', 'N/A')})",
                ).pack(anchor="w")

        if not overdue and not upcoming:
            bal = data.get("balance", 0)
            ttk.Label(
                frame,
                text=f"Balance: £{bal:.2f}" if bal else "No outstanding payments.",
            ).pack(anchor="w")

    except Exception as e:
        logger.error(f"Error creating payment alerts widget: {e}")
        ttk.Label(frame, text="Unable to load payment info.").pack(anchor="w")

    return frame
