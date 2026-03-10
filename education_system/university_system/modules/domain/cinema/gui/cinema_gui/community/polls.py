"""
Cinema Booking System - Polls and Voting
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE

def show_polls_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.polls.title"), style="Subtitle.TLabel").pack(pady=10)
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.create_poll"), style="Success.TButton", command=self.create_poll).pack(side="left", padx=5)
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)
    columns = ("ID", "Title", "Start", "End", "Votes", "Status")
    self.poll_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    for col in columns:
        self.poll_tree.heading(col, text=col)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT p.id, p.title, p.start_date, p.end_date, (SELECT SUM(votes) FROM poll_options WHERE poll_id = p.id), p.status FROM polls p ORDER BY p.start_date DESC")
    for row in cursor.fetchall():
        self.poll_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4] or 0, row[5].upper()))
    conn.close()
    self.poll_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.poll_tree.yview)
    self.poll_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.polls.view_results"), style="Primary.TButton", command=self.view_results).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.cast_vote"), style="Success.TButton", command=self.cast_vote).pack(side="left", padx=5)

def create_poll(self):
    form = tk.Toplevel(self.root)
    form.title("Create Poll")
    form.geometry("450x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()
    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=_t("cinema.polls.create"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    tk.Label(frame, text=_t("cinema.labels.title_required"), bg="#ffffff", fg="#333333").pack(anchor="w")
    title_e = ttk.Entry(frame, width=40)
    title_e.pack(pady=5)
    tk.Label(frame, text=_t("cinema.labels.end_date"), bg="#ffffff", fg="#333333").pack(anchor="w")
    end_e = ttk.Entry(frame, width=40)
    end_e.insert(0, (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
    end_e.pack(pady=5)
    tk.Label(frame, text=_t("cinema.labels.options_per_line"), bg="#ffffff", fg="#333333").pack(anchor="w")
    opts_t = tk.Text(frame, width=35, height=5, font=("Helvetica", 10))
    opts_t.insert("1.0", "Option 1\nOption 2\nOption 3")
    opts_t.pack(pady=5)
    def save():
        title = title_e.get().strip()
        opts = [o.strip() for o in opts_t.get("1.0", tk.END).strip().split('\n') if o.strip()]
        if not title or len(opts) < 2:
            messagebox.showwarning(_t("cinema.common.warning"), "Title and 2+ options required")
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO polls (title, start_date, end_date) VALUES (?, ?, ?)", (title, datetime.now().strftime("%Y-%m-%d"), end_e.get()))
        poll_id = cursor.lastrowid
        for opt in opts:
            cursor.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (?, ?)", (poll_id, opt))
        conn.commit()
        conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Poll created!")
        form.destroy()
        self.show_polls_page()
    ttk.Button(frame, text=_t("cinema.btn.create"), style="Success.TButton", command=save).pack(pady=10)

def view_results(self):
    selected = self.poll_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a poll")
        return
    poll_id = self.poll_tree.item(selected[0])['values'][0]
    poll_title = self.poll_tree.item(selected[0])['values'][1]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT option_text, votes FROM poll_options WHERE poll_id = ? ORDER BY votes DESC", (poll_id,))
    options = cursor.fetchall()
    conn.close()
    result_win = tk.Toplevel(self.root)
    result_win.title(f"Results: {poll_title}")
    result_win.geometry("400x300")
    result_win.configure(bg="#ecf0f1")
    frame = ttk.Frame(result_win, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    tk.Label(frame, text=poll_title, font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    total = sum(o[1] for o in options)
    for opt, votes in options:
        pct = (votes / total * 100) if total > 0 else 0
        tk.Label(frame, text=f"{opt}: {votes} votes ({pct:.1f}%)", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

def cast_vote(self):
    selected = self.poll_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a poll")
        return
    poll_id = self.poll_tree.item(selected[0])['values'][0]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, option_text FROM poll_options WHERE poll_id = ?", (poll_id,))
    options = cursor.fetchall()
    conn.close()
    vote_win = tk.Toplevel(self.root)
    vote_win.title("Cast Vote")
    vote_win.geometry("350x300")
    vote_win.configure(bg="#ecf0f1")
    vote_win.transient(self.root)
    vote_win.grab_set()
    frame = ttk.Frame(vote_win, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    sel_opt = tk.IntVar()
    for opt_id, opt_text in options:
        tk.Radiobutton(frame, text=opt_text, variable=sel_opt, value=opt_id, bg="#ffffff", fg="#333333", selectcolor="#0f3460").pack(anchor="w", pady=5)
    def submit():
        opt_id = sel_opt.get()
        if not opt_id:
            messagebox.showwarning(_t("cinema.common.warning"), "Select an option")
            return
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE poll_options SET votes = votes + 1 WHERE id = ?", (opt_id,))
        conn.commit()
        conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Vote recorded!")
        vote_win.destroy()
        self.show_polls_page()
    ttk.Button(frame, text=_t("cinema.btn.submit"), style="Success.TButton", command=submit).pack(pady=20)
