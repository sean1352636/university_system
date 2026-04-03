import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class GamificationDialog:
    """Dialog for viewing points and badges"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Points & Badges")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Points & Badges", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="My Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="Loading...", font=('Arial', 12), justify='left')
        self.stats_label.pack(padx=20, pady=20)

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Points history tab
        points_frame = ttk.Frame(notebook)
        notebook.add(points_frame, text="Points History")

        columns = ('Activity', 'Points', 'Date', 'Description')
        self.points_tree = ttk.Treeview(points_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.points_tree.heading(col, text=col)
            if col == 'Description':
                self.points_tree.column(col, width=300)
            else:
                self.points_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(points_frame, orient='vertical', command=self.points_tree.yview)
        self.points_tree.configure(yscrollcommand=scrollbar.set)

        self.points_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Badges tab
        badges_frame = ttk.Frame(notebook)
        notebook.add(badges_frame, text="My Badges")

        self.badges_text = scrolledtext.ScrolledText(badges_frame, wrap=tk.WORD)
        self.badges_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Leaderboard", command=self.view_leaderboard).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Available Badges", command=self.view_available_badges).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get total points
            cursor.execute('''
            SELECT SUM(points_earned), SUM(points_spent)
            FROM student_points
            WHERE student_id = ?
            ''', (student_id,))

            points_data = cursor.fetchone()
            total_earned = points_data[0] or 0
            total_spent = points_data[1] or 0
            current_balance = total_earned - total_spent

            # Get badge count
            cursor.execute('''
            SELECT COUNT(*) FROM student_badges WHERE student_id = ?
            ''', (student_id,))
            badge_count = cursor.fetchone()[0]

            stats_text = f"Total Points Earned: {total_earned}\n"
            stats_text += f"Points Spent: {total_spent}\n"
            stats_text += f"Current Balance: {current_balance}\n"
            stats_text += f"Badges Earned: {badge_count}"

            self.stats_label.config(text=stats_text)

            # Load points history
            cursor.execute('''
            SELECT activity_type, points_earned, earned_date, activity_description
            FROM student_points
            WHERE student_id = ?
            ORDER BY earned_date DESC
            LIMIT 100
            ''', (student_id,))

            points_history = cursor.fetchall()
            for item in points_history:
                self.points_tree.insert('', 'end', values=item)

            # Load badges
            cursor.execute('''
            SELECT ab.badge_name, ab.description, sb.earned_date
            FROM student_badges sb
            INNER JOIN achievement_badges ab ON sb.badge_id = ab.badge_id
            WHERE sb.student_id = ?
            ORDER BY sb.earned_date DESC
            ''', (student_id,))

            badges = cursor.fetchall()

            badges_content = "MY EARNED BADGES\n" + "="*50 + "\n\n"
            for badge in badges:
                badges_content += f"{badge[0]}\n"
                badges_content += f"Description: {badge[1]}\n"
                badges_content += f"Earned: {badge[2]}\n\n"

            if not badges:
                badges_content += "No badges earned yet. Keep participating to earn badges!"

            self.badges_text.insert(1.0, badges_content)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")

    def view_leaderboard(self):
        dialog = LeaderboardDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_available_badges(self):
        dialog = AvailableBadgesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class LeaderboardDialog:
    """Dialog for viewing leaderboard"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Leaderboard")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Student Union Leaderboard", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Top Students")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Rank', 'Student', 'Total Points', 'Badges')
        self.leaderboard_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.leaderboard_tree.heading(col, text=col)
            if col == 'Student':
                self.leaderboard_tree.column(col, width=250)
            else:
                self.leaderboard_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=scrollbar.set)

        self.leaderboard_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name,
                   SUM(sp.points_earned) as total_points,
                   (SELECT COUNT(*) FROM student_badges WHERE student_id = s.student_id) as badge_count
            FROM students s
            LEFT JOIN student_points sp ON s.student_id = sp.student_id
            GROUP BY s.student_id
            HAVING total_points > 0
            ORDER BY total_points DESC
            LIMIT 50
            ''')

            results = cursor.fetchall()

            for rank, item in enumerate(results, 1):
                values = (rank, item[0], item[1] or 0, item[2])
                self.leaderboard_tree.insert('', 'end', values=values)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load leaderboard: {str(e)}")



class AvailableBadgesDialog:
    """Dialog for viewing available badges"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Available Badges")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Available Badges", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Badges You Can Earn")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Badge', 'Description', 'Points Required', 'Category')
        self.badges_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.badges_tree.heading(col, text=col)
            if col in ('Badge', 'Description'):
                self.badges_tree.column(col, width=200)
            else:
                self.badges_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.badges_tree.yview)
        self.badges_tree.configure(yscrollcommand=scrollbar.set)

        self.badges_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT badge_name, description, points_required, category
            FROM achievement_badges
            ORDER BY points_required, badge_name
            ''')

            badges = cursor.fetchall()

            for badge in badges:
                self.badges_tree.insert('', 'end', values=badge)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load badges: {str(e)}")


# Mentorship Dialogs


class CreateBadgeDialog:
    """Dialog for creating new achievement badges (Admin only)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Badge")
        self.dialog.geometry("600x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Create New Achievement Badge", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Badge Name
        ttk.Label(main_frame, text="Badge Name:").pack(anchor='w', pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, width=50)
        self.name_entry.pack(fill='x', pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        self.description_text.pack(fill='x', pady=(0, 10))

        # Criteria
        ttk.Label(main_frame, text="Unlock Criteria:").pack(anchor='w', pady=(0, 5))
        self.criteria_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        self.criteria_text.pack(fill='x', pady=(0, 10))
        self.criteria_text.insert(1.0, "Example: Attend 10 events, Join 3 clubs, etc.")

        # Settings Frame
        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill='x', pady=(0, 10))

        # Point Value
        ttk.Label(settings_frame, text="Point Value:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.points_entry = ttk.Entry(settings_frame, width=10)
        self.points_entry.grid(row=0, column=1, sticky='w')
        self.points_entry.insert(0, "100")

        # Rarity
        ttk.Label(settings_frame, text="Rarity:").grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.rarity_var = tk.StringVar(value="Common")
        rarity_combo = ttk.Combobox(settings_frame, textvariable=self.rarity_var, width=15, state='readonly')
        rarity_combo['values'] = ('Common', 'Uncommon', 'Rare', 'Epic', 'Legendary')
        rarity_combo.grid(row=0, column=3)

        # Icon/Category
        ttk.Label(settings_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(settings_frame, textvariable=self.category_var, width=15)
        category_combo['values'] = ('Participation', 'Achievement', 'Social', 'Leadership', 'Service', 'Academic')
        category_combo.grid(row=1, column=1, sticky='w', pady=(10, 0))
        category_combo.current(0)

        # Icon
        ttk.Label(settings_frame, text="Icon:").grid(row=1, column=2, sticky='w', padx=(20, 10), pady=(10, 0))
        self.icon_entry = ttk.Entry(settings_frame, width=15)
        self.icon_entry.grid(row=1, column=3, pady=(10, 0))
        self.icon_entry.insert(0, "🏆")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Create Badge", command=self.create_badge).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create_badge(self):
        name = self.name_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        criteria = self.criteria_text.get(1.0, tk.END).strip()
        points = self.points_entry.get().strip()
        rarity = self.rarity_var.get()
        category = self.category_var.get()
        icon = self.icon_entry.get().strip()

        if not all([name, description, criteria, points]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO achievement_badges (
                badge_name, description, criteria, point_value, rarity, category,
                icon, created_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (name, description, criteria, int(points), rarity, category, icon,
                  datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Badge '{name}' created successfully!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create badge: {str(e)}")



class EditBadgeDialog:
    """Dialog for editing existing achievement badges (Admin only)"""

    def __init__(self, parent, auth_manager, badge_id):
        self.parent = parent
        self.auth = auth_manager
        self.badge_id = badge_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Badge")
        self.dialog.geometry("600x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.load_badge_data()
        self.create_widgets()

    def load_badge_data(self):
        """Load existing badge data from database"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT badge_name, description, criteria, point_value, rarity, category, icon
            FROM achievement_badges WHERE badge_id = ?
            ''', (self.badge_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                self.badge_data = {
                    'name': result[0],
                    'description': result[1],
                    'criteria': result[2],
                    'points': result[3],
                    'rarity': result[4],
                    'category': result[5],
                    'icon': result[6]
                }
            else:
                messagebox.showerror("Error", "Badge not found.")
                self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load badge data: {str(e)}")
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Edit Achievement Badge", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Badge Name
        ttk.Label(main_frame, text="Badge Name:").pack(anchor='w', pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, width=50)
        self.name_entry.pack(fill='x', pady=(0, 10))
        self.name_entry.insert(0, self.badge_data['name'])

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        self.description_text.pack(fill='x', pady=(0, 10))
        self.description_text.insert(1.0, self.badge_data['description'])

        # Criteria
        ttk.Label(main_frame, text="Unlock Criteria:").pack(anchor='w', pady=(0, 5))
        self.criteria_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        self.criteria_text.pack(fill='x', pady=(0, 10))
        self.criteria_text.insert(1.0, self.badge_data['criteria'])

        # Settings Frame
        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill='x', pady=(0, 10))

        # Point Value
        ttk.Label(settings_frame, text="Point Value:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.points_entry = ttk.Entry(settings_frame, width=10)
        self.points_entry.grid(row=0, column=1, sticky='w')
        self.points_entry.insert(0, str(self.badge_data['points']))

        # Rarity
        ttk.Label(settings_frame, text="Rarity:").grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.rarity_var = tk.StringVar(value=self.badge_data['rarity'])
        rarity_combo = ttk.Combobox(settings_frame, textvariable=self.rarity_var, width=15, state='readonly')
        rarity_combo['values'] = ('Common', 'Uncommon', 'Rare', 'Epic', 'Legendary')
        rarity_combo.grid(row=0, column=3)

        # Icon/Category
        ttk.Label(settings_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.category_var = tk.StringVar(value=self.badge_data['category'])
        category_combo = ttk.Combobox(settings_frame, textvariable=self.category_var, width=15)
        category_combo['values'] = ('Participation', 'Achievement', 'Social', 'Leadership', 'Service', 'Academic')
        category_combo.grid(row=1, column=1, sticky='w', pady=(10, 0))

        # Icon
        ttk.Label(settings_frame, text="Icon:").grid(row=1, column=2, sticky='w', padx=(20, 10), pady=(10, 0))
        self.icon_entry = ttk.Entry(settings_frame, width=15)
        self.icon_entry.grid(row=1, column=3, pady=(10, 0))
        self.icon_entry.insert(0, self.badge_data['icon'])

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Save Changes", command=self.save_badge).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def save_badge(self):
        name = self.name_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        criteria = self.criteria_text.get(1.0, tk.END).strip()
        points = self.points_entry.get().strip()
        rarity = self.rarity_var.get()
        category = self.category_var.get()
        icon = self.icon_entry.get().strip()

        if not all([name, description, criteria, points]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE achievement_badges SET
                badge_name = ?, description = ?, criteria = ?, point_value = ?,
                rarity = ?, category = ?, icon = ?
            WHERE badge_id = ?
            ''', (name, description, criteria, int(points), rarity, category, icon, self.badge_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Badge '{name}' updated successfully!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to update badge: {str(e)}")



class RewardSystemAdminDialog:
    """Dialog for managing reward system configuration (Admin only)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Reward System Administration")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Reward System Administration", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Tab 1: Activity Point Values
        points_frame = ttk.Frame(notebook)
        notebook.add(points_frame, text="Activity Points")
        self.create_points_tab(points_frame)

        # Tab 2: Badge Management
        badges_frame = ttk.Frame(notebook)
        notebook.add(badges_frame, text="Badge Management")
        self.create_badges_tab(badges_frame)

        # Tab 3: System Analytics
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text="Analytics")
        self.create_analytics_tab(analytics_frame)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def create_points_tab(self, parent):
        ttk.Label(parent, text="Configure Point Values for Activities", font=('Arial', 11, 'bold')).pack(pady=10)

        # Point values configuration
        config_frame = ttk.LabelFrame(parent, text="Activity Point Values")
        config_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        # Create entry fields for different activities
        self.point_entries = {}

        activities = [
            ("Event Attendance", "event_attendance", 10),
            ("Club Membership", "club_membership", 50),
            ("Event Organization", "event_organization", 100),
            ("Forum Post", "forum_post", 5),
            ("Discussion Reply", "discussion_reply", 2),
            ("Volunteer Hours (per hour)", "volunteer_hour", 15),
            ("Competition Participation", "competition_participation", 75),
            ("Competition Winner", "competition_winner", 200),
        ]

        for i, (label, key, default) in enumerate(activities):
            frame = ttk.Frame(config_frame)
            frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(frame, text=label, width=30).pack(side='left')
            entry = ttk.Entry(frame, width=10)
            entry.pack(side='left', padx=(10, 5))
            entry.insert(0, str(default))
            self.point_entries[key] = entry

            ttk.Label(frame, text="points").pack(side='left')

        ttk.Button(config_frame, text="Save Point Configuration", command=self.save_point_config).pack(pady=10)

    def create_badges_tab(self, parent):
        ttk.Label(parent, text="Manage Achievement Badges", font=('Arial', 11, 'bold')).pack(pady=10)

        # Badges list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        columns = ('ID', 'Name', 'Rarity', 'Points', 'Category', 'Awarded Count')
        self.badges_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.badges_tree.heading(col, text=col)
            if col == 'Name':
                self.badges_tree.column(col, width=200)
            else:
                self.badges_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.badges_tree.yview)
        self.badges_tree.configure(yscrollcommand=scrollbar.set)

        self.badges_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text="Create New Badge", command=self.create_new_badge_dialog).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_badge).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_badge).pack(side='left')

    def create_analytics_tab(self, parent):
        ttk.Label(parent, text="Reward System Analytics", font=('Arial', 11, 'bold')).pack(pady=10)

        # Analytics display
        self.analytics_text = scrolledtext.ScrolledText(parent, height=20, wrap=tk.WORD)
        self.analytics_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        ttk.Button(parent, text="Refresh Analytics", command=self.load_analytics).pack(pady=5)

    def load_data(self):
        # Load badges
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ab.badge_id, ab.badge_name, ab.rarity, ab.point_value, ab.category,
                   COUNT(sb.student_id) as awarded_count
            FROM achievement_badges ab
            LEFT JOIN student_badges sb ON ab.badge_id = sb.badge_id
            GROUP BY ab.badge_id
            ORDER BY ab.created_date DESC
            ''')

            badges = cursor.fetchall()

            for badge in badges:
                self.badges_tree.insert('', 'end', values=badge)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load badges: {str(e)}")

        # Load analytics
        self.load_analytics()

    def load_analytics(self):
        try:
            self.analytics_text.delete(1.0, tk.END)

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            analytics = "REWARD SYSTEM ANALYTICS\n"
            analytics += "=" * 80 + "\n\n"

            # Total points distributed
            cursor.execute('SELECT COALESCE(SUM(points_earned), 0) FROM student_points')
            total_points = cursor.fetchone()[0]
            analytics += f"Total Points Distributed: {total_points:,}\n\n"

            # Total badges awarded
            cursor.execute('SELECT COUNT(*) FROM student_badges')
            total_badges = cursor.fetchone()[0]
            analytics += f"Total Badges Awarded: {total_badges:,}\n\n"

            # Active students
            cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_points')
            active_students = cursor.fetchone()[0]
            analytics += f"Active Students (with points): {active_students:,}\n\n"

            # Top 10 students
            analytics += "TOP 10 STUDENTS BY POINTS:\n"
            analytics += "-" * 80 + "\n"

            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, SUM(sp.points_earned) as total_points
            FROM students s
            JOIN student_points sp ON s.student_id = sp.student_id
            GROUP BY s.student_id
            ORDER BY total_points DESC
            LIMIT 10
            ''')

            top_students = cursor.fetchall()
            for rank, (name, points) in enumerate(top_students, 1):
                analytics += f"{rank:2d}. {name:<30} {points:>10,} points\n"

            # Most popular badges
            analytics += "\n\nMOST POPULAR BADGES:\n"
            analytics += "-" * 80 + "\n"

            cursor.execute('''
            SELECT ab.badge_name, COUNT(sb.student_id) as awarded_count
            FROM achievement_badges ab
            LEFT JOIN student_badges sb ON ab.badge_id = sb.badge_id
            GROUP BY ab.badge_id
            HAVING awarded_count > 0
            ORDER BY awarded_count DESC
            LIMIT 10
            ''')

            popular_badges = cursor.fetchall()
            for badge_name, count in popular_badges:
                analytics += f"{badge_name:<40} {count:>5} awarded\n"

            # Points by activity type
            analytics += "\n\nPOINTS BY ACTIVITY TYPE:\n"
            analytics += "-" * 80 + "\n"

            cursor.execute('''
            SELECT activity_type, SUM(points_earned) as total_points
            FROM student_points
            GROUP BY activity_type
            ORDER BY total_points DESC
            ''')

            activity_points = cursor.fetchall()
            for activity, points in activity_points:
                analytics += f"{activity:<30} {points:>10,} points\n"

            self.analytics_text.insert(1.0, analytics)
            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load analytics: {str(e)}")

    def save_point_config(self):
        messagebox.showinfo("Info", "Point configuration saved!\n\nNote: This is a demo. In production, this would save to a configuration table.")

    def create_new_badge_dialog(self):
        dialog = CreateBadgeDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        # Refresh badges list
        for item in self.badges_tree.get_children():
            self.badges_tree.delete(item)
        self.load_data()

    def edit_badge(self):
        selection = self.badges_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a badge to edit.")
            return

        item = self.badges_tree.item(selection[0])
        badge_id = item['values'][0]

        dialog = EditBadgeDialog(self.dialog, self.auth, badge_id)
        self.dialog.wait_window(dialog.dialog)
        # Refresh badges list
        for item in self.badges_tree.get_children():
            self.badges_tree.delete(item)
        self.load_data()

    def delete_badge(self):
        selection = self.badges_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a badge to delete.")
            return

        item = self.badges_tree.item(selection[0])
        badge_id = item['values'][0]
        badge_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Delete badge '{badge_name}'?\n\nThis will remove it from all students who earned it."):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('DELETE FROM student_badges WHERE badge_id = ?', (badge_id,))
                cursor.execute('DELETE FROM achievement_badges WHERE badge_id = ?', (badge_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Badge deleted successfully!")
                self.badges_tree.delete(selection[0])
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to delete badge: {str(e)}")



def create_rewards_tab(self):
    """Create engagement rewards tab"""
    rewards_frame = ttk.Frame(self.notebook)
    self.notebook.add(rewards_frame, text="Rewards")
    # Left panel
    left_panel = ttk.LabelFrame(rewards_frame, text="Rewards Actions")
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
    ttk.Button(left_panel, text="My Points & Badges",
              command=self.view_my_points_and_badges).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Available Badges",
              command=self.view_available_badges).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Leaderboard",
              command=self.view_leaderboard).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Point Opportunities",
              command=self.view_point_opportunities).pack(fill='x', pady=2)
    # Admin actions separator
    ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)
    # Admin buttons (will be visible if user has admin permissions)
    ttk.Button(left_panel, text="Create New Badge (Admin)",
              command=self.create_new_badge).pack(fill='x', pady=2)
    ttk.Button(left_panel, text="Manage Reward System (Admin)",
              command=self.manage_reward_system_admin).pack(fill='x', pady=2)
    # Right panel
    right_panel = ttk.LabelFrame(rewards_frame, text="Rewards Information")
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
    self.rewards_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                 height=30, width=80)
    self.rewards_text.pack(fill='both', expand=True, padx=5, pady=5)


def create_new_badge(self):
    """Create a new achievement badge (Admin only)"""
    try:
        # Check admin permission
        if not self.auth_manager or not self.auth_manager.current_user:
            messagebox.showwarning("Warning", "Please log in first.")
            return
        if not self.auth_manager.has_permission('manage_all_clubs'):
            messagebox.showerror("Permission Denied", "Only administrators can create badges.")
            return
        dialog = CreateBadgeDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def manage_reward_system_admin(self):
    """Manage reward system settings (Admin only)"""
    try:
        # Check admin permission
        if not self.auth_manager or not self.auth_manager.current_user:
            messagebox.showwarning("Warning", "Please log in first.")
            return
        if not self.auth_manager.has_permission('manage_all_clubs'):
            messagebox.showerror("Permission Denied", "Only administrators can manage rewards.")
            return
        dialog = RewardSystemAdminDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_my_points_and_badges(self):
    """View my points and badges"""
    try:
        dialog = GamificationDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_available_badges(self):
    """View available badges"""
    try:
        dialog = AvailableBadgesDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_leaderboard(self):
    """View leaderboard"""
    try:
        dialog = LeaderboardDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_point_opportunities(self):
    """View point-earning opportunities"""
    try:
        dialog = GamificationDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


