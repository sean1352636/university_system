"""Login analytics dashboard tab for admin users.

Displays login attempt trends, failed login analysis,
user activity patterns, and MFA adoption rates.
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


def create_login_analytics_tab(parent_frame, service):
    """Create the login analytics dashboard content.

    Args:
        parent_frame: The ttk.Frame to populate.
        service: DashboardService instance.
    """
    data = service.get_login_analytics()

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
    ttk.Label(scrollable, text="User Access & Login Analytics",
              font=('Arial', 14, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # --- Summary Cards ---
    summary_frame = ttk.LabelFrame(scrollable, text="Overview (Last 30 Days)", padding="10")
    summary_frame.pack(fill=tk.X, padx=15, pady=5)

    cards = ttk.Frame(summary_frame)
    cards.pack(fill=tk.X)
    for i in range(5):
        cards.columnconfigure(i, weight=1)

    sr = data['success_rate']
    mfa = data['mfa_adoption']
    _create_stat_card(cards, "Total Logins", str(sr['total']), 0, 0)
    _create_stat_card(cards, "Successful", str(sr['successful']), 0, 1)
    _create_stat_card(cards, "Failed", str(sr['failed']), 0, 2)
    _create_stat_card(cards, "Success Rate", f"{sr['rate_pct']}%", 0, 3)
    _create_stat_card(cards, "MFA Adoption", f"{mfa['rate_pct']}%", 0, 4)

    # --- Active Users ---
    active_frame = ttk.LabelFrame(scrollable, text="Active Users", padding="10")
    active_frame.pack(fill=tk.X, padx=15, pady=5)

    active_cards = ttk.Frame(active_frame)
    active_cards.pack(fill=tk.X)
    for i in range(3):
        active_cards.columnconfigure(i, weight=1)

    _create_stat_card(active_cards, "Active (24h)", str(data['active_users_24h']), 0, 0)
    _create_stat_card(active_cards, "Active (7d)", str(data['active_users_7d']), 0, 1)
    _create_stat_card(
        active_cards, "MFA Enabled",
        f"{mfa['enabled']} / {mfa['total']}",
        0, 2,
    )

    # --- Daily Login Trends ---
    trends_frame = ttk.LabelFrame(scrollable, text="Daily Login Trends (Last 30 Days)", padding="10")
    trends_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['daily_login_trends']:
        cols = ('day', 'successful', 'failed', 'total')
        tree = ttk.Treeview(trends_frame, columns=cols, show='headings',
                            height=min(10, len(data['daily_login_trends'])))
        tree.heading('day', text='Date')
        tree.heading('successful', text='Successful')
        tree.heading('failed', text='Failed')
        tree.heading('total', text='Total')
        tree.column('day', width=120)
        tree.column('successful', width=100, anchor='center')
        tree.column('failed', width=100, anchor='center')
        tree.column('total', width=100, anchor='center')
        for r in data['daily_login_trends']:
            tree.insert('', tk.END, values=(
                r.get('day', ''), r.get('successful', 0),
                r.get('failed', 0), r.get('total', 0),
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(trends_frame, text="No login data available.").pack(anchor="w")

    # --- Hourly Activity Pattern ---
    hourly_frame = ttk.LabelFrame(scrollable, text="Hourly Activity Pattern (Last 7 Days)", padding="10")
    hourly_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['hourly_activity']:
        # Build a simple text-based bar chart
        max_count = max((h['count'] for h in data['hourly_activity']), default=1)
        bar_text = ""
        for h in data['hourly_activity']:
            hour = h['hour']
            count = h['count']
            bar_len = int((count / max_count) * 30) if max_count > 0 else 0
            bar_text += f"  {hour:02d}:00  {'|' * bar_len} {count}\n"

        text_widget = tk.Text(hourly_frame, wrap=tk.WORD, height=12, width=60,
                              font=('Courier', 9))
        text_widget.pack(fill=tk.X)
        text_widget.insert(tk.END, bar_text)
        text_widget.config(state=tk.DISABLED)
    else:
        ttk.Label(hourly_frame, text="No hourly data available.").pack(anchor="w")

    # --- Failed Logins by User ---
    failed_user_frame = ttk.LabelFrame(
        scrollable, text="Top Failed Logins by User (Last 7 Days)", padding="10"
    )
    failed_user_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['failed_logins_by_user']:
        cols = ('username', 'fail_count', 'last_attempt')
        tree = ttk.Treeview(failed_user_frame, columns=cols, show='headings',
                            height=min(8, len(data['failed_logins_by_user'])))
        tree.heading('username', text='Username')
        tree.heading('fail_count', text='Failed Attempts')
        tree.heading('last_attempt', text='Last Attempt')
        tree.column('username', width=180)
        tree.column('fail_count', width=120, anchor='center')
        tree.column('last_attempt', width=180)
        for r in data['failed_logins_by_user']:
            tree.insert('', tk.END, values=(
                r.get('username', ''), r.get('fail_count', 0),
                r.get('last_attempt', ''),
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(failed_user_frame, text="No failed logins recorded.").pack(anchor="w")

    # --- Top Failed IPs ---
    ip_frame = ttk.LabelFrame(scrollable, text="Top Failed Login IPs (Last 7 Days)", padding="10")
    ip_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['top_failed_ips']:
        cols = ('ip_address', 'fail_count')
        tree = ttk.Treeview(ip_frame, columns=cols, show='headings',
                            height=min(6, len(data['top_failed_ips'])))
        tree.heading('ip_address', text='IP Address')
        tree.heading('fail_count', text='Failed Attempts')
        tree.column('ip_address', width=200)
        tree.column('fail_count', width=120, anchor='center')
        for r in data['top_failed_ips']:
            tree.insert('', tk.END, values=(
                r.get('ip_address', 'N/A'), r.get('fail_count', 0),
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(ip_frame, text="No IP data available.").pack(anchor="w")

    # --- Recent Failed Login Attempts ---
    recent_frame = ttk.LabelFrame(scrollable, text="Recent Failed Login Attempts", padding="10")
    recent_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

    if data['recent_failed_logins']:
        cols = ('username', 'attempt_time', 'ip_address')
        tree = ttk.Treeview(recent_frame, columns=cols, show='headings',
                            height=min(10, len(data['recent_failed_logins'])))
        tree.heading('username', text='Username')
        tree.heading('attempt_time', text='Time')
        tree.heading('ip_address', text='IP Address')
        tree.column('username', width=160)
        tree.column('attempt_time', width=180)
        tree.column('ip_address', width=150)
        for r in data['recent_failed_logins']:
            tree.insert('', tk.END, values=(
                r.get('username', ''), r.get('attempt_time', ''),
                r.get('ip_address', 'N/A'),
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(recent_frame, text="No recent failed logins.").pack(anchor="w")


def _create_stat_card(parent, label, value, row, col):
    """Create a small stat card widget."""
    frame = ttk.Frame(parent, relief="groove", borderwidth=1)
    frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
    ttk.Label(frame, text=value, font=('Arial', 16, 'bold')).pack(pady=(8, 2))
    ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))
