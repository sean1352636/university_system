"""Rubric management"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from collections import deque



class RubricManager:
    """Rubric management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def manage_rubrics(self):
        """Manage grading rubrics"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text=_("rubric.title"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Rubrics list
        rubrics_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_("rubric.existing_rubrics"), padding=10)
        rubrics_frame.pack(fill='both', expand=True)
        
        # Treeview for rubrics
        columns = ('ID', 'Name', 'Total Points', 'Created', 'Usage')
        rubric_tree = ttk.Treeview(rubrics_frame, columns=columns, show='headings')
        
        for col in columns:
            rubric_tree.heading(col, text=col)
            rubric_tree.column(col, width=120)
        
        rubric_tree.pack(fill='both', expand=True)
        
        # Load rubrics
        self.load_rubrics_data(rubric_tree)
        
        # Buttons
        buttons_frame = ttk.Frame(self.gui.layout.content_area)
        buttons_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.create_new_rubric"),
                  command=self.show_create_rubric).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.edit_rubric"),
                  command=lambda: self.edit_rubric(rubric_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.delete_rubric"),
                  command=lambda: self.delete_rubric(rubric_tree)).pack(side='left')
    

    def load_rubrics_data(self, tree):
        """Load rubrics data into treeview"""
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT r.id, r.name, r.total_points, r.created_at, 
                   COUNT(a.id) as usage_count
            FROM rubrics r
            LEFT JOIN assignments a ON r.id = a.rubric_id
            WHERE r.is_active = 1
            GROUP BY r.id, r.name, r.total_points, r.created_at
            ORDER BY r.created_at DESC
            ''')
            
            rubrics = cursor.fetchall()
            
            for rubric in rubrics:
                tree.insert('', 'end', values=rubric)
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror(_("common.error"), _("rubric.failed_load_rubrics", error=str(e)))
    

    def edit_rubric(self, tree):
        """Edit selected rubric"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("rubric.select_rubric"))
            return
        
        item = tree.item(selection[0])
        rubric_id = item['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rubrics WHERE id = ?', (rubric_id,))
            record = cursor.fetchone()
            conn.close()
        except Exception as exc:
            messagebox.showerror(_("common.error"), _("rubric.failed_load_rubric", error=str(exc)))
            return

        if not record:
            messagebox.showerror(_("common.error"), _("rubric.rubric_not_exists"))
            return
    
        editor = tk.Toplevel(self.root)
        editor.title(f"Edit Rubric - {record['name']}")
        editor.geometry("460x400")
        editor.transient(self.root)
        editor.grab_set()
    
        form_frame = ttk.Frame(editor, padding=15)
        form_frame.pack(fill='both', expand=True)
    
        name_var = tk.StringVar(value=record['name'])
        ttk.Label(form_frame, text=_("assignment_gui.labels.name")).grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        points_var = tk.StringVar(value=str(record['total_points']))
        ttk.Label(form_frame, text=_("assignment_gui.labels.total_points")).grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(form_frame, textvariable=points_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        active_var = tk.BooleanVar(value=bool(record['is_active']))
        ttk.Checkbutton(form_frame, text=_("assignment_gui.labels.active"), variable=active_var).grid(row=2, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text=_("assignment_gui.labels.description")).grid(row=3, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, height=6, width=40)
        desc_text.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        if record['description']:
            desc_text.insert(tk.END, record['description'])
    
        def save_rubric_changes():
            try:
                name = name_var.get().strip()
                if not name:
                    raise ValueError("Rubric name cannot be empty.")
    
                total_points = float(points_var.get())
                if total_points <= 0:
                    raise ValueError("Total points must be positive.")
    
                description = desc_text.get("1.0", tk.END).strip()
                is_active = 1 if active_var.get() else 0
    
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE rubrics
                        SET name = ?, description = ?, total_points = ?, is_active = ?
                        WHERE id = ?
                        """,
                        (name, description, total_points, is_active, rubric_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
    
                editor.destroy()
                self.load_rubrics_data(tree)
                messagebox.showinfo(_("common.success"), _("rubric.rubric_updated"))
            except ValueError as ve:
                messagebox.showerror(_("assignment_gui.messages.validation_error"), str(ve))
            except Exception as exc:
                messagebox.showerror(_("common.error"), _("rubric.failed_update_rubric", error=str(exc)))

        button_frame = ttk.Frame(editor)
        button_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(button_frame, text=_("assignment_gui.buttons.save_changes"), command=save_rubric_changes, style='Accent.TButton').pack(side='left')
        ttk.Button(button_frame, text=_("assignment_gui.buttons.cancel"), command=editor.destroy).pack(side='right')
    

    def delete_rubric(self, tree):
        """Delete selected rubric"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("rubric.select_rubric"))
            return

        item = tree.item(selection[0])
        rubric_id = item['values'][0]
        rubric_name = item['values'][1]

        if messagebox.askyesno(_("common.confirm"), _("rubric.confirm_delete_rubric", name=rubric_name)):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('UPDATE rubrics SET is_active = 0 WHERE id = ?', (rubric_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("rubric.rubric_deleted"))
                self.load_rubrics_data(tree)

            except Exception as e:
                messagebox.showerror(_("common.error"), _("rubric.failed_delete_rubric", error=str(e)))
    
    # ADVANCED ANALYTICS METHODS

    def show_rubric_editor(self):
        """Show rubric editor dialog"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_("rubric.rubric_editor"))
            dialog.geometry("800x600")
            dialog.transient(self.root)

            ttk.Label(dialog, text=_("rubric.rubric_editor"),
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Rubric details
            details_frame = ttk.LabelFrame(dialog, text=_("rubric.rubric_details"), padding=10)
            details_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(details_frame, text=_("rubric.rubric_name")).grid(row=0, column=0, sticky='w', pady=5)
            rubric_name_var = tk.StringVar()
            ttk.Entry(details_frame, textvariable=rubric_name_var, width=40).grid(row=0, column=1, pady=5, padx=(10, 0))

            ttk.Label(details_frame, text=_("assignment_gui.labels.total_points")).grid(row=1, column=0, sticky='w', pady=5)
            rubric_points_var = tk.StringVar(value="100")
            ttk.Entry(details_frame, textvariable=rubric_points_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

            # Criteria section
            criteria_frame = ttk.LabelFrame(dialog, text=_("rubric.rubric_criteria"), padding=10)
            criteria_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
            # Criteria list
            columns = ('Criterion', 'Description', 'Points', 'Weight %')
            criteria_tree = ttk.Treeview(criteria_frame, columns=columns, show='headings', height=10)
    
            for col in columns:
                criteria_tree.heading(col, text=col)
                criteria_tree.column(col, width=150)
    
            criteria_tree.pack(fill='both', expand=True, pady=5)
    
            # Sample criteria
            sample_criteria = [
                ("Content Quality", "Clear, accurate, and comprehensive", "25", "25"),
                ("Organization", "Well-structured and logical flow", "25", "25"),
                ("Analysis", "Critical thinking and depth", "25", "25"),
                ("Writing Quality", "Grammar, style, and clarity", "25", "25")
            ]
    
            for criterion in sample_criteria:
                criteria_tree.insert('', 'end', values=criterion)
    
            # Buttons
            button_frame = ttk.Frame(criteria_frame)
            button_frame.pack(fill='x', pady=5)
    
            ttk.Button(button_frame, text=_("assignment_gui.buttons.add_criterion"),
                      command=lambda: messagebox.showinfo(_("common.info"), "Add Criterion - To be implemented")).pack(side='left', padx=2)
            ttk.Button(button_frame, text=_("assignment_gui.buttons.edit_selected"),
                      command=lambda: messagebox.showinfo(_("common.info"), "Edit - To be implemented")).pack(side='left', padx=2)
            ttk.Button(button_frame, text=_("assignment_gui.buttons.delete_selected"),
                      command=lambda: messagebox.showinfo(_("common.info"), "Delete - To be implemented")).pack(side='left', padx=2)

            # Bottom buttons
            bottom_frame = ttk.Frame(dialog)
            bottom_frame.pack(pady=10)

            ttk.Button(bottom_frame, text=_("assignment_gui.buttons.save_rubric"),
                      command=lambda: messagebox.showinfo(_("common.info"), "Rubric saved")).pack(side='left', padx=5)
            ttk.Button(bottom_frame, text=_("assignment_gui.buttons.close"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("rubric.failed_open_editor", error=str(e)))
    

    def show_create_rubric(self):
        """Render the rubric creation workflow."""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_("rubric.create_rubric"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        form_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_("rubric.rubric_details"), padding=20)
        form_frame.pack(fill='x', pady=(0, 20))

        ttk.Label(form_frame, text=_("rubric.rubric_name")).grid(row=0, column=0, sticky='w', pady=5)
        rubric_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=rubric_name_var, width=50).grid(row=0, column=1, sticky='w', padx=(10, 0))

        ttk.Label(form_frame, text=_("assignment_gui.labels.total_points")).grid(row=1, column=0, sticky='w', pady=5)
        total_points_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=total_points_var, width=10).grid(row=1, column=1, sticky='w', padx=(10, 0))

        ttk.Label(form_frame, text=_("assignment_gui.labels.description")).grid(row=2, column=0, sticky='nw', pady=5)
        description_text = scrolledtext.ScrolledText(form_frame, width=50, height=5, wrap=tk.WORD)
        description_text.grid(row=2, column=1, sticky='we', padx=(10, 0))
    
        form_frame.grid_columnconfigure(1, weight=1)
    
        criteria_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_("rubric.rubric_criteria"), padding=10)
        criteria_frame.pack(fill='both', expand=True, pady=(0, 20))
    
        columns = ('Criterion', 'Description', 'Points', 'Weight')
        criteria_tree = ttk.Treeview(criteria_frame, columns=columns, show='headings', height=10)
        for col in columns:
            criteria_tree.heading(col, text=col)
            width = 160 if col in ('Criterion', 'Description') else 80
            criteria_tree.column(col, width=width, anchor='w')
        criteria_tree.pack(fill='both', expand=True)
    
        criteria_data = []
    
        def refresh_criteria():
            for item in criteria_tree.get_children():
                criteria_tree.delete(item)
            for idx, entry in enumerate(criteria_data, start=1):
                criteria_tree.insert(
                    '',
                    'end',
                    iid=str(idx - 1),
                    values=(entry['name'], entry['description'], entry['points'], entry['weight'])
                )
    
        def open_criteria_dialog(existing=None, index=None):
            dialog = tk.Toplevel(self.root)
            dialog.title(_("rubric.criterion") if existing is None else _("rubric.edit_criterion"))
            dialog.geometry("420x320")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_("rubric.criterion_name")).pack(anchor='w', padx=10, pady=(10, 5))
            name_var = tk.StringVar(value=(existing['name'] if existing else ""))
            ttk.Entry(dialog, textvariable=name_var).pack(fill='x', padx=10)

            ttk.Label(dialog, text=_("assignment_gui.labels.description")).pack(anchor='w', padx=10, pady=(10, 5))
            desc_text = scrolledtext.ScrolledText(dialog, height=5, wrap=tk.WORD)
            desc_text.pack(fill='both', expand=True, padx=10)
            if existing:
                desc_text.insert(tk.END, existing['description'])
    
            points_frame = ttk.Frame(dialog)
            points_frame.pack(fill='x', padx=10, pady=(10, 5))

            ttk.Label(points_frame, text=_("assignment_gui.labels.points")).grid(row=0, column=0, sticky='w')
            points_var = tk.StringVar(value=str(existing['points']) if existing else "0")
            ttk.Entry(points_frame, textvariable=points_var, width=10).grid(row=0, column=1, padx=(10, 0))

            ttk.Label(points_frame, text=_("assignment_gui.labels.weight")).grid(row=0, column=2, sticky='w', padx=(20, 0))
            weight_var = tk.StringVar(value=str(existing['weight']) if existing else "0")
            ttk.Entry(points_frame, textvariable=weight_var, width=10).grid(row=0, column=3, padx=(10, 0))

            def save():
                name = name_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()
                if not name:
                    messagebox.showerror(_("assignment_gui.messages.validation_error"), _("assignment_gui.messages.criterion_required"), parent=dialog)
                    return
                try:
                    points_value = float(points_var.get())
                    weight_value = float(weight_var.get())
                except ValueError:
                    messagebox.showerror(_("assignment_gui.messages.validation_error"), _("assignment_gui.messages.points_must_be_numbers"), parent=dialog)
                    return
                criterion = {
                    'name': name,
                    'description': description,
                    'points': points_value,
                    'weight': weight_value
                }
                if index is None:
                    criteria_data.append(criterion)
                else:
                    criteria_data[index] = criterion
                refresh_criteria()
                dialog.destroy()
    
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=10)
            ttk.Button(button_frame, text=_("assignment_gui.buttons.save"), command=save, style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text=_("assignment_gui.buttons.cancel"), command=dialog.destroy).pack(side='right')

        def add_criterion():
            open_criteria_dialog()

        def edit_selected_criterion():
            selection = criteria_tree.selection()
            if not selection:
                messagebox.showwarning(_("assignment_gui.messages.no_selection"), _("rubric.select_criterion"))
                return
            idx = int(selection[0])
            open_criteria_dialog(existing=criteria_data[idx], index=idx)

        def delete_selected_criterion():
            selection = criteria_tree.selection()
            if not selection:
                messagebox.showwarning(_("assignment_gui.messages.no_selection"), _("rubric.select_criterion_delete"))
                return
            idx = int(selection[0])
            if messagebox.askyesno(_("common.confirm"), _("rubric.confirm_delete_criterion")):
                criteria_data.pop(idx)
                refresh_criteria()

        buttons_frame = ttk.Frame(criteria_frame)
        buttons_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.add_criterion"), command=add_criterion).pack(side='left')
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.edit_selected"), command=edit_selected_criterion).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text=_("assignment_gui.buttons.delete_selected"), command=delete_selected_criterion).pack(side='left')
    
        # Status area
        status_frame = ttk.Frame(self.gui.layout.content_area)
        status_frame.pack(fill='x')
        status_label = ttk.Label(status_frame, text="", style='Info.TLabel')
        status_label.pack(anchor='w', pady=(10, 0))
    
        def show_status(message, style='Info.TLabel'):
            status_label.config(text=message, style=style)
    
        def save_rubric():
            name = rubric_name_var.get().strip()
            description = description_text.get("1.0", tk.END).strip()
            if not name:
                show_status(_("assignment_gui.messages.rubric_name_required"), 'Error.TLabel')
                return
            try:
                total_points = float(total_points_var.get())
                if total_points <= 0:
                    raise ValueError
            except ValueError:
                show_status(_("assignment_gui.messages.total_points_positive"), 'Error.TLabel')
                return
            if not criteria_data:
                show_status(_("assignment_gui.messages.add_criterion_first"), 'Error.TLabel')
                return

            sum_points = sum(c['points'] for c in criteria_data)
            if sum_points != total_points:
                if not messagebox.askyesno(
                        _("common.confirm"),
                        _("assignment_gui.messages.point_mismatch", total=total_points, sum=sum_points)):
                    show_status(_("assignment_gui.messages.rubric_not_saved"), 'Warning.TLabel')
                    return
    
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                created_by = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
                cursor.execute(
                    '''
                    INSERT INTO rubrics (name, description, total_points, is_active, created_by)
                    VALUES (?, ?, ?, 1, ?)
                    ''',
                    (name, description, total_points, created_by)
                )
                rubric_id = cursor.lastrowid
                for order, criterion in enumerate(criteria_data):
                    cursor.execute(
                        '''
                        INSERT INTO rubric_criteria (
                            rubric_id, criteria_name, description, max_points, weight, display_order
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            rubric_id,
                            criterion['name'],
                            criterion['description'],
                            criterion['points'],
                            criterion['weight'],
                            order
                        )
                    )
                conn.commit()
                conn.close()
                show_status(_("common.success"), 'Success.TLabel')
                messagebox.showinfo(_("common.success"), _("assignment_gui.messages.rubric_created", name=name, count=len(criteria_data)))
                self.manage_rubrics()
            except Exception as exc:
                show_status(str(exc), 'Error.TLabel')

        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(action_frame, text=_("assignment_gui.buttons.save_rubric"), command=save_rubric, style='Accent.TButton').pack(side='left')
        ttk.Button(action_frame, text=_("assignment_gui.buttons.cancel"), command=self.manage_rubrics).pack(side='left', padx=10)
    

    def create_rubric(self, *args, **kwargs):
        """Navigate to the rubric creation screen."""
        self._launch_gui_feature(self.show_create_rubric, "rubric creation")
    
    
