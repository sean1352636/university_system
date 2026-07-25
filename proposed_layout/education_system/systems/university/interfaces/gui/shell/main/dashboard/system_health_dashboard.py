"""Real-time system health monitoring dashboard tab for admin users.

Displays active user sessions, database connection pool status,
query performance metrics, error rate monitoring, and table statistics.
"""

import tkinter as tk
from tkinter import ttk
import logging

from education_system.systems.university.infrastructure.sql_safety import validate_table_name

logger = logging.getLogger(__name__)


def create_system_health_tab(parent_frame, service):
    """Create the system health monitoring content.

    Args:
        parent_frame: The ttk.Frame to populate.
        service: DashboardService instance.
    """
    data = service.get_system_health_data()

    canvas = tk.Canvas(parent_frame)
    scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)

    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Title
    ttk.Label(scrollable, text="DB Performance",
              font=('Arial', 14, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # --- Top-level summary ---
    summary_frame = ttk.LabelFrame(scrollable, text="System Summary", padding="10")
    summary_frame.pack(fill=tk.X, padx=15, pady=5)

    cards = ttk.Frame(summary_frame)
    cards.pack(fill=tk.X)
    for i in range(4):
        cards.columnconfigure(i, weight=1)

    _create_stat_card(cards, "Active Users (24h)", str(data.get('active_sessions_24h', 0)), 0, 0)
    _create_stat_card(cards, "DB Size", f"{data.get('db_size_mb', 0)} MB", 0, 1)

    err = data.get('error_rate', {})
    _create_stat_card(cards, "Total Queries", str(err.get('total_queries', 0)), 0, 2)
    _create_stat_card(cards, "Slow Queries", str(err.get('slow_queries', 0)), 0, 3)

    # --- Connection Pool Status ---
    pool = data.get('pool_stats', {})
    pool_frame = ttk.LabelFrame(scrollable, text="Connection Pool Status", padding="10")
    pool_frame.pack(fill=tk.X, padx=15, pady=5)

    current = pool.get('current', {})
    cumulative = pool.get('cumulative', {})
    wait_times = pool.get('wait_times', {})

    pool_cards = ttk.Frame(pool_frame)
    pool_cards.pack(fill=tk.X)
    for i in range(5):
        pool_cards.columnconfigure(i, weight=1)

    _create_stat_card(pool_cards, "Total Connections",
                      str(current.get('total_connections', 'N/A')), 0, 0)
    _create_stat_card(pool_cards, "Active",
                      str(current.get('active_connections', 'N/A')), 0, 1)
    _create_stat_card(pool_cards, "Idle",
                      str(current.get('idle_connections', 'N/A')), 0, 2)
    _create_stat_card(pool_cards, "Utilization",
                      f"{current.get('utilization_percent', 0)}%", 0, 3)
    _create_stat_card(pool_cards, "Waiting Threads",
                      str(current.get('waiting_threads', 0)), 0, 4)

    # Pool cumulative stats
    if cumulative:
        cum_frame = ttk.LabelFrame(pool_frame, text="Cumulative Pool Stats", padding="10")
        cum_frame.pack(fill=tk.X, pady=(10, 0))

        cum_cards = ttk.Frame(cum_frame)
        cum_cards.pack(fill=tk.X)
        for i in range(4):
            cum_cards.columnconfigure(i, weight=1)

        _create_stat_card(cum_cards, "Total Acquires",
                          str(cumulative.get('total_acquires', 0)), 0, 0)
        _create_stat_card(cum_cards, "Total Errors",
                          str(cumulative.get('total_errors', 0)), 0, 1)
        _create_stat_card(cum_cards, "Timeouts",
                          str(cumulative.get('total_timeouts', 0)), 0, 2)
        _create_stat_card(cum_cards, "Pool Exhausted",
                          str(cumulative.get('pool_exhausted_count', 0)), 0, 3)

    # Wait times
    if wait_times and any(v for v in wait_times.values()):
        wait_frame = ttk.LabelFrame(pool_frame, text="Connection Wait Times", padding="10")
        wait_frame.pack(fill=tk.X, pady=(10, 0))

        wait_cards = ttk.Frame(wait_frame)
        wait_cards.pack(fill=tk.X)
        for i in range(4):
            wait_cards.columnconfigure(i, weight=1)

        _create_stat_card(wait_cards, "Avg Wait",
                          f"{wait_times.get('avg_ms', 0):.1f}ms", 0, 0)
        _create_stat_card(wait_cards, "Max Wait",
                          f"{wait_times.get('max_ms', 0):.1f}ms", 0, 1)
        _create_stat_card(wait_cards, "P95 Wait",
                          f"{wait_times.get('p95_ms', 0):.1f}ms", 0, 2)
        _create_stat_card(wait_cards, "P99 Wait",
                          f"{wait_times.get('p99_ms', 0):.1f}ms", 0, 3)

    # --- Query Performance ---
    qs = data.get('query_stats', {})
    query_frame = ttk.LabelFrame(scrollable, text="Query Performance", padding="10")
    query_frame.pack(fill=tk.X, padx=15, pady=5)

    if qs:
        q_cards = ttk.Frame(query_frame)
        q_cards.pack(fill=tk.X)
        for i in range(4):
            q_cards.columnconfigure(i, weight=1)

        _create_stat_card(q_cards, "Total Queries",
                          str(qs.get('total_queries', 0)), 0, 0)
        _create_stat_card(q_cards, "Slow Queries",
                          str(qs.get('slow_queries', 0)), 0, 1)
        avg_time = qs.get('avg_time_ms', 0)
        _create_stat_card(q_cards, "Avg Time",
                          f"{avg_time:.1f}ms" if isinstance(avg_time, (int, float)) else "N/A", 0, 2)
        slow_pct = qs.get('slow_percentage', 0)
        _create_stat_card(q_cards, "Slow %",
                          f"{slow_pct:.1f}%" if isinstance(slow_pct, (int, float)) else "N/A", 0, 3)

        # Slow query threshold
        threshold = qs.get('slow_threshold_ms', 100)
        ttk.Label(query_frame,
                  text=f"Slow query threshold: {threshold}ms",
                  font=('Arial', 9, 'italic')).pack(anchor="w", pady=(5, 0))

        # Top slow queries if available
        top_queries = qs.get('top_queries', [])
        if top_queries:
            tq_frame = ttk.LabelFrame(query_frame, text="Top Queries by Total Time", padding="10")
            tq_frame.pack(fill=tk.X, pady=(10, 0))

            cols = ('pattern', 'executions', 'avg_ms', 'total_ms')
            tree = ttk.Treeview(tq_frame, columns=cols, show='headings',
                                height=min(8, len(top_queries)))
            tree.heading('pattern', text='Query Pattern')
            tree.heading('executions', text='Executions')
            tree.heading('avg_ms', text='Avg (ms)')
            tree.heading('total_ms', text='Total (ms)')
            tree.column('pattern', width=300)
            tree.column('executions', width=80, anchor='center')
            tree.column('avg_ms', width=80, anchor='center')
            tree.column('total_ms', width=80, anchor='center')
            for q in top_queries:
                tree.insert('', tk.END, values=(
                    q.get('pattern', '')[:80],
                    q.get('total_executions', 0),
                    f"{q.get('avg_time_ms', 0):.1f}",
                    f"{q.get('total_time_ms', 0):.0f}",
                ))
            tree.pack(fill=tk.X)
    else:
        ttk.Label(query_frame,
                  text="Query monitoring data not yet available. "
                       "Metrics accumulate as queries execute.").pack(anchor="w")

    # --- Database Table Row Counts ---
    rows_data = data.get('table_row_counts', [])
    if rows_data:
        table_frame = ttk.LabelFrame(scrollable, text="Database Table Statistics", padding="10")
        table_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

        ttk.Label(table_frame, text="Double-click a table to view its data",
                  font=('Arial', 9, 'italic')).pack(anchor="w", pady=(0, 5))

        cols = ('table', 'rows')
        tree = ttk.Treeview(table_frame, columns=cols, show='headings',
                            height=min(10, len(rows_data)))
        tree.heading('table', text='Table')
        tree.heading('rows', text='Row Count')
        tree.column('table', width=250)
        tree.column('rows', width=120, anchor='center')
        for r in rows_data:
            tree.insert('', tk.END, values=(
                r.get('table', ''), f"{r.get('rows', 0):,}",
            ))
        tree.pack(fill=tk.X)

        tree.bind("<Double-1>", lambda e: _on_table_double_click(e, parent_frame))

    # Refresh button
    btn_frame = ttk.Frame(scrollable)
    btn_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

    def refresh():
        # Clear and rebuild
        for widget in parent_frame.winfo_children():
            widget.destroy()
        create_system_health_tab(parent_frame, service)

    ttk.Button(btn_frame, text="Refresh", command=refresh).pack(anchor="e")


def _on_table_double_click(event, parent_frame):
    """Handle double-click on a table row to show table data."""
    tree = event.widget
    selection = tree.selection()
    if not selection:
        return
    item = tree.item(selection[0])
    table_name = item['values'][0] if item['values'] else None
    if not table_name:
        return
    _show_table_data(parent_frame.winfo_toplevel(), str(table_name))


def _show_table_data(parent, table_name):
    """Open a Toplevel window showing all rows from the selected table."""
    from education_system.systems.university.infrastructure.database.db import get_connection

    # Validate table name against known safe tables to prevent injection
    allowed_tables = {
        'users', 'students', 'modules', 'student_modules',
        'assignments', 'assignment_submissions', 'login_attempts',
        'support_tickets', 'payments', 'courses', 'enrollments',
        'office_hours', 'office_hour_bookings', 'teaching_assistants',
        'announcements', 'chat_rooms', 'chat_messages',
    }
    if table_name not in allowed_tables:
        logger.warning("Table drill-down blocked for unrecognized table: %s", table_name)
        return

    win = tk.Toplevel(parent)
    win.title(f"Table Data: {table_name}")
    win.geometry("1100x600")
    win.minsize(800, 400)

    try:
        safe_table = validate_table_name(table_name)
        with get_connection() as conn:
            # Get column names
            cursor = conn.execute("PRAGMA table_info([" + safe_table + "])")
            col_info = cursor.fetchall()
            col_names = [c[1] for c in col_info]

            # Fetch data (limit to 500 rows)
            rows = conn.execute(
                "SELECT * FROM [" + safe_table + "] LIMIT 500"
            ).fetchall()

        if not col_names:
            ttk.Label(win, text=f"Table '{table_name}' has no columns.").pack(padx=20, pady=20)
            return

        # Header
        header_frame = ttk.Frame(win)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(header_frame, text=f"{table_name}",
                  font=('Arial', 13, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header_frame, text=f"({len(rows)} rows shown, max 500)",
                  font=('Arial', 10)).pack(side=tk.LEFT, padx=(10, 0))

        # Treeview with scrollbars
        tree_frame = ttk.Frame(win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        data_tree = ttk.Treeview(
            tree_frame, columns=col_names, show='headings',
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set,
        )
        y_scroll.config(command=data_tree.yview)
        x_scroll.config(command=data_tree.xview)

        for col in col_names:
            data_tree.heading(col, text=col)
            data_tree.column(col, width=120, minwidth=60)

        for row in rows:
            values = []
            for i in range(len(col_names)):
                val = row[i] if i < len(row) else ''
                # Truncate long values for display
                s = str(val) if val is not None else ''
                if len(s) > 100:
                    s = s[:97] + '...'
                values.append(s)
            data_tree.insert('', tk.END, values=values)

        data_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    except Exception as exc:
        logger.error("Error loading table data for %s: %s", table_name, exc)
        ttk.Label(win, text=f"Error loading data: {exc}").pack(padx=20, pady=20)


def _create_stat_card(parent, label, value, row, col):
    """Create a small stat card widget."""
    frame = ttk.Frame(parent, relief="groove", borderwidth=1)
    frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
    ttk.Label(frame, text=value, font=('Arial', 16, 'bold')).pack(pady=(8, 2))
    ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))
