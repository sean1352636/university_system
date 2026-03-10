from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from .base import ParentPortalGUI

def show_goals_interface(self):
    """Show academic goals interface"""
    self.clear_content()
    self.update_status(_t("parent.goals.title"))

    title = ttk.Label(self.content_frame, text=_t("parent.goals.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text=_t("parent.goals.no_students_linked")).pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text=_t("parent.goals.select_student")).pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Goals display frame
    goals_frame = ttk.LabelFrame(self.content_frame, text=_t("parent.goals.title"), padding=15)
    goals_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_goals():
        for widget in goals_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(goals_frame, text=_t("parent.goals.please_select_child")).pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='academic_goals'
            """)

            if cursor.fetchone():
                # Use correct column names from academic_goals table schema
                cursor.execute("""
                SELECT goal_title, COALESCE(target_grade, 'General'), target_date,
                       COALESCE(current_progress, '0'), status, description
                FROM academic_goals
                WHERE student_id = ?
                ORDER BY target_date
                LIMIT 20
                """, (student_id,))

                goals = cursor.fetchall()

                if goals:
                    for goal in goals:
                        goal_card = ttk.LabelFrame(goals_frame, text=goal[0] or 'Unnamed Goal', padding=10)
                        goal_card.pack(fill=tk.X, pady=5)

                        target_grade = goal[1] or _t("common.na")
                        target_date = goal[2] or _t("parent.goals.not_set")
                        ttk.Label(goal_card, text=f"{_t('parent.goals.target_grade')}: {target_grade} | {_t('parent.goals.target_date')}: {target_date}",
                                 font=('Arial', 9, 'bold')).pack(anchor='w')

                        # Parse progress - handle various formats
                        progress_str = str(goal[3]) if goal[3] else '0'
                        try:
                            progress_val = int(float(progress_str.replace('%', '')))
                        except (ValueError, TypeError):
                            progress_val = 0

                        status = goal[4] or _t("parent.goals.status_active")
                        ttk.Label(goal_card, text=f"{_t('parent.goals.progress')}: {progress_val}% | {_t('parent.goals.status')}: {status}",
                                 font=('Arial', 9)).pack(anchor='w')
                        if goal[5]:
                            ttk.Label(goal_card, text=goal[5], wraplength=600).pack(anchor='w', pady=3)

                        # Progress bar
                        progress_bar = ttk.Progressbar(goal_card, length=400, mode='determinate')
                        progress_bar['value'] = min(progress_val, 100)
                        progress_bar.pack(anchor='w', pady=5)
                else:
                    ttk.Label(goals_frame, text=_t("parent.goals.no_goals_set"),
                             font=('Arial', 11)).pack(pady=50)
                    ttk.Button(goals_frame, text=_t("parent.goals.set_goal"),
                              command=lambda: self.set_academic_goal(student_id)).pack()
            else:
                ttk.Label(goals_frame, text=_t("parent.goals.system_not_configured"),
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(goals_frame, text=_t("parent.goals.error_loading", error=str(e)),
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text=_t("parent.goals.load_goals"), command=load_goals).pack(side=tk.LEFT, padx=5)
    load_goals()
ParentPortalGUI.show_goals_interface = show_goals_interface

def set_academic_goal(self, student_id):
    """Set a new academic goal"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title(_t("parent.goals.set_academic_goal"))
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("parent.goals.set_academic_goal"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='academic_goals'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE academic_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                goal_title TEXT NOT NULL,
                category TEXT,
                target_date TEXT,
                description TEXT,
                status TEXT DEFAULT 'Active',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("parent.goals.db_init_failed", error=str(e)))
        dialog.destroy()
        return

    # Create form fields
    fields = {}

    # Goal Title
    ttk.Label(main_frame, text=_t("parent.goals.goal_title_required")).pack(anchor='w', pady=(5, 0))
    fields['goal_title'] = ttk.Entry(main_frame, width=50)
    fields['goal_title'].pack(fill=tk.X, pady=(0, 10))

    # Category
    ttk.Label(main_frame, text=_t("parent.goals.category")).pack(anchor='w', pady=(5, 0))
    fields['category'] = ttk.Combobox(main_frame, width=50, state="readonly")
    fields['category']['values'] = [_t('parent.goals.cat_academic_performance'), _t('parent.goals.cat_homework_completion'), _t('parent.goals.cat_reading'),
                                   _t('parent.goals.cat_math'), _t('parent.goals.cat_science'), _t('parent.goals.cat_writing'), _t('parent.goals.cat_test_scores'), _t('parent.goals.cat_behavior'), _t('parent.goals.cat_other')]
    fields['category'].pack(fill=tk.X, pady=(0, 10))

    # Target Date
    ttk.Label(main_frame, text=_t("parent.goals.target_date_format")).pack(anchor='w', pady=(5, 0))
    fields['target_date'] = ttk.Entry(main_frame, width=50)
    fields['target_date'].pack(fill=tk.X, pady=(0, 10))

    # Description
    ttk.Label(main_frame, text=_t("parent.goals.description_required")).pack(anchor='w', pady=(5, 0))
    fields['description'] = scrolledtext.ScrolledText(main_frame, width=50, height=8)
    fields['description'].pack(fill=tk.X, pady=(0, 10))

    def save_goal():
        # Validate required fields
        if not fields['goal_title'].get():
            messagebox.showwarning(_t("common.validation_error"), _t("parent.goals.enter_goal_title"))
            return

        if not fields['description'].get('1.0', tk.END).strip():
            messagebox.showwarning(_t("common.validation_error"), _t("parent.goals.provide_description"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new goal
            cursor.execute("""
            INSERT INTO academic_goals (student_id, goal_title, category, target_date, description)
            VALUES (?, ?, ?, ?, ?)
            """, (
                student_id,
                fields['goal_title'].get(),
                fields['category'].get(),
                fields['target_date'].get(),
                fields['description'].get('1.0', tk.END).strip()
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("common.success"), _t("parent.goals.goal_set_success"))
            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("parent.goals.save_failed", error=str(e)))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text=_t("parent.goals.save_goal"), command=save_goal).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.set_academic_goal = set_academic_goal
