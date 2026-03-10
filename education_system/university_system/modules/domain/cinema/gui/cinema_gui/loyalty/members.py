"""
Cinema Booking System - Membership/Loyalty Program Management
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from ..database import DB_FILE
from ..constants import MEMBERSHIP_TIERS

def show_members_page(self):
    """Display members/loyalty program management page."""
    self.clear_content()

    ttk.Label(self.content_frame, text=_t("cinema.members.title"),
             style="Subtitle.TLabel").pack(pady=10)

    # Action buttons
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)

    ttk.Button(btn_frame, text=_t("cinema.members.add_member"), style="Success.TButton",
              command=self.show_add_member_form).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.members.member_lookup"), style="Primary.TButton",
              command=self.show_member_lookup).pack(side="left", padx=5)

    # Membership tiers info
    tiers_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
    tiers_frame.pack(fill="x", pady=10)

    tk.Label(tiers_frame, text=_t("cinema.members.membership_tiers"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w")

    for i, (tier, info) in enumerate(MEMBERSHIP_TIERS.items()):
        tier_colors = {"Bronze": "#cd7f32", "Silver": "#c0c0c0", "Gold": "#ffd700", "Platinum": "#e5e4e2"}
        tier_frame = ttk.Frame(tiers_frame, style="Card.TFrame")
        tier_frame.pack(fill="x", pady=2)

        tk.Label(tier_frame, text=f"{tier}", font=("Helvetica", 11, "bold"),
                bg="#ffffff", fg=tier_colors.get(tier, "#ffffff"), width=10).pack(side="left")
        tk.Label(tier_frame, text=f"Min Points: {info['min_points']} | Discount: {info['discount']}% | Points Multiplier: {info['points_multiplier']}x",
                bg="#ffffff", fg="#7f8c8d").pack(side="left", padx=10)

    # Search
    search_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    search_frame.pack(fill="x", pady=10)

    tk.Label(search_frame, text=_t("cinema.buttons.search_label"), bg="#ffffff", fg="#333333").pack(side="left")
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side="left", padx=10)

    # Members list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Name", "Email", "Tier", "Points", "Total Spent", "Bookings", "Status")
    self.member_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

    for col in columns:
        self.member_tree.heading(col, text=col)
    self.member_tree.column("ID", width=50)
    self.member_tree.column("Name", width=150)
    self.member_tree.column("Email", width=200)
    self.member_tree.column("Tier", width=80)
    self.member_tree.column("Points", width=80)
    self.member_tree.column("Total Spent", width=100)
    self.member_tree.column("Bookings", width=80)
    self.member_tree.column("Status", width=80)

    def search_members():
        for item in self.member_tree.get_children():
            self.member_tree.delete(item)

        query = search_entry.get().strip()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if query:
            cursor.execute('''
                SELECT id, name, email, tier, points, total_spent, bookings_count, status
                FROM members WHERE name LIKE ? OR email LIKE ?
                ORDER BY points DESC
            ''', (f"%{query}%", f"%{query}%"))
        else:
            cursor.execute('''
                SELECT id, name, email, tier, points, total_spent, bookings_count, status
                FROM members ORDER BY points DESC LIMIT 100
            ''')

        for row in cursor.fetchall():
            self.member_tree.insert("", "end", values=(
                row[0], row[1], row[2], row[3], row[4],
                f"£{row[5]:.2f}", row[6], row[7].upper()
            ))
        conn.close()

    ttk.Button(search_frame, text=_t("cinema.buttons.search"), style="Primary.TButton",
              command=search_members).pack(side="left", padx=5)
    ttk.Button(search_frame, text=_t("cinema.buttons.show_all"), style="Secondary.TButton",
              command=lambda: (search_entry.delete(0, tk.END), search_members())).pack(side="left", padx=5)

    self.member_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.member_tree.yview)
    self.member_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)

    ttk.Button(action_frame, text=_t("cinema.members.view_details"), style="Secondary.TButton",
              command=self.view_member_details).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.members.edit_member"), style="Secondary.TButton",
              command=self.edit_selected_member).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.members.add_points"), style="Success.TButton",
              command=self.add_member_points).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.members.deactivate"), style="Danger.TButton",
              command=self.deactivate_member).pack(side="left", padx=5)

    search_members()

def show_add_member_form(self):
    """Show form to add a new member."""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add New Member")
    form_window.geometry("450x400")
    form_window.configure(bg="#ecf0f1")
    form_window.transient(self.root)
    form_window.grab_set()

    fields_frame = ttk.Frame(form_window, style="Card.TFrame", padding=20)
    fields_frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(fields_frame, text=_t("cinema.members.new_member_registration"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    tk.Label(fields_frame, text=_t("cinema.members.name_required"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    name_entry = ttk.Entry(fields_frame, width=35)
    name_entry.grid(row=1, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.members.email_required"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    email_entry = ttk.Entry(fields_frame, width=35)
    email_entry.grid(row=2, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.members.phone_label"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    phone_entry = ttk.Entry(fields_frame, width=35)
    phone_entry.grid(row=3, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.members.birthday_label"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    birthday_entry = ttk.Entry(fields_frame, width=35)
    birthday_entry.insert(0, "YYYY-MM-DD")
    birthday_entry.grid(row=4, column=1, pady=5)

    tk.Label(fields_frame, text=_t("cinema.members.initial_points_label"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    points_entry = ttk.Entry(fields_frame, width=35)
    points_entry.insert(0, "100")  # Welcome bonus
    points_entry.grid(row=5, column=1, pady=5)

    def save_member():
        name = name_entry.get().strip()
        email = email_entry.get().strip()

        if not name or not email:
            messagebox.showwarning(_t("cinema.common.warning"), _t("cinema.messages.warnings.name_email_required"))
            return

        try:
            points = int(points_entry.get() or 100)
        except (ValueError, TypeError):
            points = 100

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO members (name, email, phone, birthday, points, tier)
                VALUES (?, ?, ?, ?, ?, 'Bronze')
            ''', (name, email, phone_entry.get().strip(), birthday_entry.get().strip(), points))
            conn.commit()
            messagebox.showinfo(_t("cinema.common.success"), f"Member {name} added with {points} welcome points!")
            form_window.destroy()
            self.show_members_page()
        except sqlite3.IntegrityError:
            messagebox.showerror(_t("cinema.common.error"), _t("cinema.messages.warnings.email_already_registered"))
        finally:
            conn.close()

    btn_frame = ttk.Frame(fields_frame, style="Card.TFrame")
    btn_frame.grid(row=6, column=0, columnspan=2, pady=20)

    ttk.Button(btn_frame, text=_t("cinema.members.register_btn"), style="Success.TButton",
              command=save_member).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.cancel"), style="Secondary.TButton",
              command=form_window.destroy).pack(side="left", padx=5)

def show_member_lookup(self):
    """Quick member lookup dialog."""
    lookup_window = tk.Toplevel(self.root)
    lookup_window.title("Member Lookup")
    lookup_window.geometry("500x400")
    lookup_window.configure(bg="#ecf0f1")
    lookup_window.transient(self.root)
    lookup_window.grab_set()

    frame = ttk.Frame(lookup_window, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.members.member_lookup"), font=("Helvetica", 14, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(pady=10)

    search_frame = ttk.Frame(frame, style="Card.TFrame")
    search_frame.pack(fill="x", pady=10)

    tk.Label(search_frame, text=_t("cinema.common.email_label"), bg="#ffffff", fg="#333333").pack(side="left")
    email_entry = ttk.Entry(search_frame, width=30)
    email_entry.pack(side="left", padx=10)

    result_frame = ttk.Frame(frame, style="Card.TFrame")
    result_frame.pack(fill="both", expand=True, pady=10)

    def lookup():
        for widget in result_frame.winfo_children():
            widget.destroy()

        email = email_entry.get().strip()
        if not email:
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE email = ?", (email,))
        member = cursor.fetchone()
        conn.close()

        if member:
            tier_colors = {"Bronze": "#cd7f32", "Silver": "#c0c0c0", "Gold": "#ffd700", "Platinum": "#e5e4e2"}

            tk.Label(result_frame, text=member[2], font=("Helvetica", 16, "bold"),
                    bg="#ffffff", fg="#2c3e50").pack()
            tk.Label(result_frame, text=member[5], font=("Helvetica", 14),
                    bg="#ffffff", fg=tier_colors.get(member[5], "#ffffff")).pack()
            tk.Label(result_frame, text=f"Points: {member[4]}", font=("Helvetica", 12),
                    bg="#ffffff", fg="#27ae60").pack(pady=5)
            tk.Label(result_frame, text=f"Total Spent: £{member[6]:.2f}",
                    bg="#ffffff", fg="#7f8c8d").pack()
            tk.Label(result_frame, text=f"Bookings: {member[7]}",
                    bg="#ffffff", fg="#7f8c8d").pack()

            # Show discount
            discount = MEMBERSHIP_TIERS.get(member[5], {}).get('discount', 0)
            if discount > 0:
                tk.Label(result_frame, text=f"Member Discount: {discount}%",
                        font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(pady=10)
        else:
            tk.Label(result_frame, text=_t("cinema.members.not_found"), bg="#ffffff", fg="#dc3545").pack()
            ttk.Button(result_frame, text=_t("cinema.members.register_new"), style="Success.TButton",
                      command=lambda: (lookup_window.destroy(), self.show_add_member_form())).pack(pady=10)

    ttk.Button(search_frame, text=_t("cinema.buttons.lookup"), style="Primary.TButton",
              command=lookup).pack(side="left", padx=5)

def view_member_details(self):
    """View detailed member information."""
    selected = self.member_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a member")
        return

    member_id = self.member_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
    member = cursor.fetchone()

    # Get booking history
    cursor.execute('''
        SELECT b.booking_ref, m.title, s.show_time, b.total_amount, b.status
        FROM bookings b
        JOIN screenings s ON b.screening_id = s.id
        JOIN movies m ON s.movie_id = m.id
        WHERE b.customer_email = ?
        ORDER BY b.booking_time DESC LIMIT 10
    ''', (member[1],))
    bookings = cursor.fetchall()
    conn.close()

    if not member:
        return

    detail_window = tk.Toplevel(self.root)
    detail_window.title(f"Member: {member[2]}")
    detail_window.geometry("600x500")
    detail_window.configure(bg="#ecf0f1")
    detail_window.transient(self.root)

    frame = ttk.Frame(detail_window, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tier_colors = {"Bronze": "#cd7f32", "Silver": "#c0c0c0", "Gold": "#ffd700", "Platinum": "#e5e4e2"}

    tk.Label(frame, text=member[2], font=("Helvetica", 18, "bold"),
            bg="#ffffff", fg="#2c3e50").pack()
    tk.Label(frame, text=member[5], font=("Helvetica", 14),
            bg="#ffffff", fg=tier_colors.get(member[5], "#ffffff")).pack()

    stats_frame = ttk.Frame(frame, style="Card.TFrame")
    stats_frame.pack(fill="x", pady=20)

    stats = [
        ("Points", member[4]),
        ("Total Spent", f"£{member[6]:.2f}"),
        ("Bookings", member[7]),
    ]

    for i, (label, value) in enumerate(stats):
        stat_box = ttk.Frame(stats_frame, style="Card.TFrame")
        stat_box.pack(side="left", expand=True)
        tk.Label(stat_box, text=str(value), font=("Helvetica", 20, "bold"),
                bg="#ffffff", fg="#27ae60").pack()
        tk.Label(stat_box, text=label, bg="#ffffff", fg="#7f8c8d").pack()

    tk.Label(frame, text=_t("cinema.booking.recent"), font=("Helvetica", 12, "bold"),
            bg="#ffffff", fg="#e74c3c").pack(anchor="w", pady=(10, 5))

    for booking in bookings:
        tk.Label(frame, text=f"{booking[0]} - {booking[1]} - {booking[2]} - £{booking[3]:.2f} ({booking[4]})",
                bg="#ffffff", fg="#7f8c8d", font=("Helvetica", 9)).pack(anchor="w")

def edit_selected_member(self):
    """Edit selected member."""
    selected = self.member_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a member")
        return
    messagebox.showinfo(_t("cinema.common.info"), "Edit member details in the database directly for now")

def add_member_points(self):
    """Add points to selected member."""
    selected = self.member_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a member")
        return

    member_id = self.member_tree.item(selected[0])['values'][0]
    member_name = self.member_tree.item(selected[0])['values'][1]

    dialog = tk.Toplevel(self.root)
    dialog.title("Add Points")
    dialog.geometry("300x150")
    dialog.configure(bg="#ecf0f1")
    dialog.transient(self.root)
    dialog.grab_set()

    frame = ttk.Frame(dialog, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=f"Add points to {member_name}", bg="#ffffff", fg="#333333").pack()
    points_entry = ttk.Entry(frame, width=20)
    points_entry.pack(pady=10)

    def add_points():
        try:
            points = int(points_entry.get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid points value")
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET points = points + ? WHERE id = ?", (points, member_id))

        # Update tier based on new points
        cursor.execute("SELECT points FROM members WHERE id = ?", (member_id,))
        new_points = cursor.fetchone()[0]

        new_tier = "Bronze"
        for tier, info in MEMBERSHIP_TIERS.items():
            if new_points >= info['min_points']:
                new_tier = tier

        cursor.execute("UPDATE members SET tier = ? WHERE id = ?", (new_tier, member_id))
        conn.commit()
        conn.close()

        messagebox.showinfo(_t("cinema.common.success"), f"Added {points} points. New tier: {new_tier}")
        dialog.destroy()
        self.show_members_page()

    ttk.Button(frame, text=_t("cinema.members.add_points"), style="Success.TButton",
              command=add_points).pack()

def deactivate_member(self):
    """Deactivate selected member."""
    selected = self.member_tree.selection()
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select a member")
        return

    member_id = self.member_tree.item(selected[0])['values'][0]

    if not messagebox.askyesno(_t("cinema.common.confirm"), "Deactivate this member?"):
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE members SET status = 'inactive' WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()

    self.show_members_page()

def get_member_discount(self, email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT tier FROM members WHERE email = ? AND status = 'active'", (email,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return MEMBERSHIP_TIERS.get(result[0], {}).get('discount', 0)
    return 0
