"""Domain-specific operational dashboards tab for admin users.

Displays course utilization, grade distributions by instructor,
student retention metrics, financial aid funnel, and support ticket stats.
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


def create_operations_tab(parent_frame, service):
    """Create the operational dashboards content with sub-tabs.

    Args:
        parent_frame: The ttk.Frame to populate.
        service: DashboardService instance.
    """
    data = service.get_operational_metrics()

    # Sub-notebook for different operational domains
    notebook = ttk.Notebook(parent_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Course Utilization tab
    course_frame = ttk.Frame(notebook)
    notebook.add(course_frame, text="Course Utilization")
    _build_course_utilization(course_frame, data)

    # Grade Distribution tab
    grade_frame = ttk.Frame(notebook)
    notebook.add(grade_frame, text="Grade Distribution")
    _build_grade_distribution(grade_frame, data)

    # Student Retention tab
    retention_frame = ttk.Frame(notebook)
    notebook.add(retention_frame, text="Student Retention")
    _build_retention_metrics(retention_frame, data)

    # Financial Aid tab
    aid_frame = ttk.Frame(notebook)
    notebook.add(aid_frame, text="Financial Aid")
    _build_financial_aid(aid_frame, data)

    # Support Tickets tab
    ticket_frame = ttk.Frame(notebook)
    notebook.add(ticket_frame, text="Support Tickets")
    _build_ticket_stats(ticket_frame, data)


def _build_course_utilization(parent, data):
    """Build course utilization rates view."""
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)
    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    ttk.Label(scrollable, text="Course Utilization Rates",
              font=('Arial', 13, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    courses = data.get('course_utilization', [])
    if courses:
        # Summary cards
        total = len(courses)
        over_80 = sum(1 for c in courses if (c.get('utilization_pct') or 0) >= 80)
        under_20 = sum(1 for c in courses if (c.get('utilization_pct') or 0) < 20 and (c.get('capacity') or 0) > 0)
        avg_util = (
            round(sum(c.get('utilization_pct', 0) or 0 for c in courses if (c.get('capacity') or 0) > 0) /
                  max(sum(1 for c in courses if (c.get('capacity') or 0) > 0), 1), 1)
        )

        cards_frame = ttk.Frame(scrollable)
        cards_frame.pack(fill=tk.X, padx=15, pady=5)
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)

        _create_stat_card(cards_frame, "Total Courses", str(total), 0, 0)
        _create_stat_card(cards_frame, "Avg Utilization", f"{avg_util}%", 0, 1)
        _create_stat_card(cards_frame, "High Demand (>80%)", str(over_80), 0, 2)
        _create_stat_card(cards_frame, "Low Demand (<20%)", str(under_20), 0, 3)

        # Table
        table_frame = ttk.LabelFrame(scrollable, text="All Courses", padding="10")
        table_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ('module_code', 'module_name', 'enrolled', 'capacity', 'utilization_pct')
        tree = ttk.Treeview(table_frame, columns=cols, show='headings',
                            height=min(15, len(courses)))
        tree.heading('module_code', text='Code')
        tree.heading('module_name', text='Course Name')
        tree.heading('enrolled', text='Enrolled')
        tree.heading('capacity', text='Capacity')
        tree.heading('utilization_pct', text='Utilization %')
        tree.column('module_code', width=100)
        tree.column('module_name', width=250)
        tree.column('enrolled', width=80, anchor='center')
        tree.column('capacity', width=80, anchor='center')
        tree.column('utilization_pct', width=100, anchor='center')
        for c in courses:
            tree.insert('', tk.END, values=(
                c.get('module_code', ''), c.get('module_name', ''),
                c.get('enrolled', 0), c.get('capacity', 'N/A'),
                f"{c.get('utilization_pct', 0)}%",
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(scrollable, text="No course data available.").pack(anchor="w", padx=15)


def _build_grade_distribution(parent, data):
    """Build grade distribution views."""
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)
    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    ttk.Label(scrollable, text="Grade Distribution",
              font=('Arial', 13, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # Overall grade distribution
    grades = data.get('grade_distribution', [])
    if grades:
        overall_frame = ttk.LabelFrame(scrollable, text="Overall Grade Distribution", padding="10")
        overall_frame.pack(fill=tk.X, padx=15, pady=5)

        total_graded = sum(g.get('count', 0) for g in grades)

        # Visual bar representation
        text_widget = tk.Text(overall_frame, wrap=tk.WORD, height=len(grades) + 1,
                              width=60, font=('Courier', 10))
        text_widget.pack(fill=tk.X)
        for g in grades:
            band = g.get('grade_band', '?')
            count = g.get('count', 0)
            pct = round((count / total_graded) * 100, 1) if total_graded > 0 else 0
            bar_len = int(pct / 2)
            text_widget.insert(tk.END, f"  {band:<12} {'#' * bar_len} {count} ({pct}%)\n")
        text_widget.config(state=tk.DISABLED)
    else:
        ttk.Label(scrollable, text="No grade data available.").pack(anchor="w", padx=15)

    # By instructor
    by_instr = data.get('grade_distribution_by_instructor', [])
    if by_instr:
        instr_frame = ttk.LabelFrame(
            scrollable, text="Grade Averages by Instructor", padding="10"
        )
        instr_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ('instructor', 'avg_grade', 'submissions_graded', 'min_grade', 'max_grade')
        tree = ttk.Treeview(instr_frame, columns=cols, show='headings',
                            height=min(10, len(by_instr)))
        tree.heading('instructor', text='Instructor')
        tree.heading('avg_grade', text='Avg Grade')
        tree.heading('submissions_graded', text='Graded')
        tree.heading('min_grade', text='Min')
        tree.heading('max_grade', text='Max')
        tree.column('instructor', width=160)
        tree.column('avg_grade', width=100, anchor='center')
        tree.column('submissions_graded', width=80, anchor='center')
        tree.column('min_grade', width=80, anchor='center')
        tree.column('max_grade', width=80, anchor='center')
        for r in by_instr:
            tree.insert('', tk.END, values=(
                r.get('instructor', ''), r.get('avg_grade', ''),
                r.get('submissions_graded', 0),
                r.get('min_grade', ''), r.get('max_grade', ''),
            ))
        tree.pack(fill=tk.X)


def _build_retention_metrics(parent, data):
    """Build student retention metrics view."""
    container = ttk.Frame(parent, padding="20")
    container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(container, text="Student Retention Metrics",
              font=('Arial', 13, 'bold')).pack(anchor="w", pady=(0, 10))

    rm = data.get('retention_metrics', {})

    cards_frame = ttk.Frame(container)
    cards_frame.pack(fill=tk.X, pady=5)
    for i in range(4):
        cards_frame.columnconfigure(i, weight=1)

    _create_stat_card(cards_frame, "Total Students", str(rm.get('total_students', 0)), 0, 0)
    _create_stat_card(cards_frame, "Currently Active", str(rm.get('active_students', 0)), 0, 1)
    _create_stat_card(cards_frame, "Dropped/Withdrawn", str(rm.get('dropped_students', 0)), 0, 2)
    _create_stat_card(cards_frame, "Retention Rate", f"{rm.get('retention_rate_pct', 0)}%", 0, 3)

    # Visual retention bar
    detail_frame = ttk.LabelFrame(container, text="Retention Breakdown", padding="15")
    detail_frame.pack(fill=tk.X, pady=10)

    total = rm.get('total_students', 0)
    active = rm.get('active_students', 0)
    dropped = rm.get('dropped_students', 0)
    inactive = total - active - dropped if total > active + dropped else 0

    text_widget = tk.Text(detail_frame, wrap=tk.WORD, height=5, width=60,
                          font=('Courier', 10))
    text_widget.pack(fill=tk.X)

    if total > 0:
        active_pct = round((active / total) * 100, 1)
        dropped_pct = round((dropped / total) * 100, 1)
        inactive_pct = round((inactive / total) * 100, 1)
        text_widget.insert(tk.END,
                           f"  Active:     {'#' * int(active_pct / 2)} {active} ({active_pct}%)\n"
                           f"  Dropped:    {'#' * int(dropped_pct / 2)} {dropped} ({dropped_pct}%)\n"
                           f"  Other:      {'#' * int(inactive_pct / 2)} {inactive} ({inactive_pct}%)\n")
    else:
        text_widget.insert(tk.END, "  No student data available.\n")
    text_widget.config(state=tk.DISABLED)


def _build_financial_aid(parent, data):
    """Build financial aid funnel view."""
    container = ttk.Frame(parent, padding="20")
    container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(container, text="Financial Aid Funnel",
              font=('Arial', 13, 'bold')).pack(anchor="w", pady=(0, 10))

    fa = data.get('financial_aid_funnel', {})

    # Summary cards
    cards_frame = ttk.Frame(container)
    cards_frame.pack(fill=tk.X, pady=5)
    for i in range(5):
        cards_frame.columnconfigure(i, weight=1)

    _create_stat_card(cards_frame, "Total Applications", str(fa.get('total_applications', 0)), 0, 0)
    _create_stat_card(cards_frame, "Pending", str(fa.get('pending', 0)), 0, 1)
    _create_stat_card(cards_frame, "Approved", str(fa.get('approved', 0)), 0, 2)
    _create_stat_card(cards_frame, "Disbursed", str(fa.get('disbursed', 0)), 0, 3)
    _create_stat_card(cards_frame, "Cancelled", str(fa.get('cancelled', 0)), 0, 4)

    # Financial totals
    totals_frame = ttk.LabelFrame(container, text="Financial Totals", padding="15")
    totals_frame.pack(fill=tk.X, pady=10)

    awarded = fa.get('total_awarded', 0)
    disbursed = fa.get('total_disbursed', 0)

    totals_cards = ttk.Frame(totals_frame)
    totals_cards.pack(fill=tk.X)
    for i in range(2):
        totals_cards.columnconfigure(i, weight=1)

    _create_stat_card(totals_cards, "Total Awarded",
                      f"${awarded:,.2f}" if isinstance(awarded, (int, float)) else "$0.00", 0, 0)
    _create_stat_card(totals_cards, "Total Disbursed",
                      f"${disbursed:,.2f}" if isinstance(disbursed, (int, float)) else "$0.00", 0, 1)

    # Funnel visualization
    funnel_frame = ttk.LabelFrame(container, text="Application Pipeline", padding="15")
    funnel_frame.pack(fill=tk.X, pady=10)

    total = fa.get('total_applications', 0)
    text_widget = tk.Text(funnel_frame, wrap=tk.WORD, height=6, width=60,
                          font=('Courier', 10))
    text_widget.pack(fill=tk.X)

    stages = [
        ('Applications', total),
        ('Pending Review', fa.get('pending', 0)),
        ('Approved', fa.get('approved', 0)),
        ('Disbursed', fa.get('disbursed', 0)),
    ]
    for stage_name, count in stages:
        bar_len = int((count / total) * 40) if total > 0 else 0
        pct = round((count / total) * 100, 1) if total > 0 else 0
        text_widget.insert(tk.END, f"  {stage_name:<18} {'#' * bar_len} {count} ({pct}%)\n")
    text_widget.config(state=tk.DISABLED)


def _build_ticket_stats(parent, data):
    """Build support ticket statistics view."""
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)
    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    ttk.Label(scrollable, text="Support Ticket Analytics",
              font=('Arial', 13, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    ts = data.get('ticket_stats', {})

    # Summary cards
    cards_frame = ttk.Frame(scrollable)
    cards_frame.pack(fill=tk.X, padx=15, pady=5)
    for i in range(5):
        cards_frame.columnconfigure(i, weight=1)

    _create_stat_card(cards_frame, "Total Tickets", str(ts.get('total', 0)), 0, 0)
    _create_stat_card(cards_frame, "Open", str(ts.get('open', 0)), 0, 1)
    _create_stat_card(cards_frame, "In Progress", str(ts.get('in_progress', 0)), 0, 2)
    _create_stat_card(cards_frame, "Resolved", str(ts.get('resolved', 0)), 0, 3)

    avg_hours = ts.get('avg_resolution_hours')
    avg_display = f"{avg_hours}h" if avg_hours is not None else "N/A"
    _create_stat_card(cards_frame, "Avg Resolution", avg_display, 0, 4)

    # By category
    by_cat = data.get('tickets_by_category', [])
    if by_cat:
        cat_frame = ttk.LabelFrame(scrollable, text="Tickets by Category", padding="10")
        cat_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ('category', 'count')
        tree = ttk.Treeview(cat_frame, columns=cols, show='headings',
                            height=min(8, len(by_cat)))
        tree.heading('category', text='Category')
        tree.heading('count', text='Count')
        tree.column('category', width=250)
        tree.column('count', width=100, anchor='center')
        for r in by_cat:
            tree.insert('', tk.END, values=(
                r.get('category', ''), r.get('count', 0),
            ))
        tree.pack(fill=tk.X)

    # By priority
    by_pri = data.get('tickets_by_priority', [])
    if by_pri:
        pri_frame = ttk.LabelFrame(scrollable, text="Tickets by Priority", padding="10")
        pri_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

        cols = ('priority', 'count')
        tree = ttk.Treeview(pri_frame, columns=cols, show='headings',
                            height=min(6, len(by_pri)))
        tree.heading('priority', text='Priority')
        tree.heading('count', text='Count')
        tree.column('priority', width=250)
        tree.column('count', width=100, anchor='center')
        for r in by_pri:
            tree.insert('', tk.END, values=(
                r.get('priority', ''), r.get('count', 0),
            ))
        tree.pack(fill=tk.X)


def _create_stat_card(parent, label, value, row, col):
    """Create a small stat card widget."""
    frame = ttk.Frame(parent, relief="groove", borderwidth=1)
    frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
    ttk.Label(frame, text=value, font=('Arial', 16, 'bold')).pack(pady=(8, 2))
    ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))
