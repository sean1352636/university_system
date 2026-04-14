"""
Cinema Booking System - Referral Program Management
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
import random
import string

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE
from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.constants import REFERRAL_REWARD

def show_referrals_page(self):
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.referrals.title"), style="Subtitle.TLabel").pack(pady=10)

    info_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    info_frame.pack(fill="x", pady=10)
    tk.Label(info_frame, text=_t("cinema.referrals.title"), font=("Helvetica", 12, "bold"), bg="#ffffff", fg="#e74c3c").pack(anchor="w")
    tk.Label(info_frame, text=f"Reward: {REFERRAL_REWARD}", font=("Helvetica", 11), bg="#ffffff", fg="#27ae60").pack(anchor="w")
    tk.Label(info_frame, text=_t("cinema.referrals.reward_description"),
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.new_referral"), style="Success.TButton", command=self.create_referral).pack(side="left", padx=5)

    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Code", "Referrer Email", "Referee Email", "Status", "Reward Given", "Created")
    self.referral_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.referral_tree.heading(col, text=col)
        self.referral_tree.column(col, width=100)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cinema_referrals ORDER BY created_at DESC")
        for row in cursor.fetchall():
            self.referral_tree.insert("", "end", values=(row[0], row[1], row[2], row[3] or "-",
                                                        row[4].upper(), "Yes" if row[5] else "No", row[6][:10]))
    finally:
        conn.close()

    self.referral_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.referral_tree.yview)
    self.referral_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.btn.mark_used"), command=self.use_referral).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.give_reward"), command=self.give_referral_reward).pack(side="left", padx=5)

def create_referral(self):
    form = tk.Toplevel(self.root)
    form.title("New Referral")
    form.geometry("400x300")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.referrals.create_code"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=_t("cinema.labels.referrer_email"), bg="#ffffff", fg="#333333").pack(anchor="w")
    email_e = ttk.Entry(frame, width=35)
    email_e.pack(pady=5)

    def create():
        if not email_e.get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Enter referrer email")
            return
        code = 'REF' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO cinema_referrals (referral_code, referrer_email, status, created_at)
                            VALUES (?, ?, 'pending', datetime('now'))""", (code, email_e.get().strip()))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), f"Referral code created: {code}")
        form.destroy()
        self.show_referrals_page()

    ttk.Button(frame, text=_t("cinema.btn.generate_code"), style="Success.TButton", command=create).pack(pady=20)

def use_referral(self):
    selected = self.referral_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a referral")
        return
    ref_id = self.referral_tree.item(selected[0])['values'][0]

    referee_email = simpledialog.askstring("Referee", "Enter referee email:")
    if referee_email:
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE cinema_referrals SET referee_email = ?, status = 'used' WHERE id = ?",
                          (referee_email, ref_id))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Referral marked as used")
        self.show_referrals_page()

def give_referral_reward(self):
    selected = self.referral_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Select a referral")
        return
    ref_id = self.referral_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE cinema_referrals SET reward_given = 1, status = 'completed' WHERE id = ?", (ref_id,))
        conn.commit()
    finally:
        conn.close()
    messagebox.showinfo(_t("cinema.common.success"), "Reward marked as given")
    self.show_referrals_page()
