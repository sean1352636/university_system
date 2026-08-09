"""Budget category management"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.finance.interfaces.gui.finance.budget_manager.constants import (
    create_budget_category,
    deactivate_budget_category,
    edit_budget_category,
    update_actual_amounts,
    view_budget_categories,
)


class BudgetCategoriesMixin:
    """Budget category management methods"""

    def gui_manage_budget_categories(self):
        """Full GUI for managing budget categories"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.manage_budget_categories', default="Manage Budget Categories"))
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Header
        header_frame = tk.Frame(dialog, bg='#2c3e50', height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.budget_categories_management', default="Budget Categories Management"),
                font=('TkDefaultFont', 16, 'bold'), bg='#2c3e50', fg='white').pack(pady=15)

        # Toolbar
        toolbar = tk.Frame(dialog, bg='white', height=50)
        toolbar.pack(fill='x', padx=10, pady=5)
        toolbar.pack_propagate(False)

        def add_category():
            """Add new budget category"""
            add_dialog = tk.Toplevel(dialog)
            add_dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.add_budget_category', default="Add Budget Category"))
            add_dialog.geometry("500x400")
            add_dialog.transient(dialog)
            add_dialog.grab_set()

            form_frame = ttk.LabelFrame(add_dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.category_details', default="Category Details"), padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)

            # Category name
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_name', default="Category Name:")).grid(row=0, column=0, sticky='w', pady=5, padx=5)
            name_var = tk.StringVar()
            name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
            name_entry.grid(row=0, column=1, pady=5, padx=5)
            name_entry.focus()

            # Category type
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_type', default="Category Type:")).grid(row=1, column=0, sticky='w', pady=5, padx=5)
            type_var = tk.StringVar(value=_t('gui.finance.finance.budget_manager.categories.values.expense', default="expense"))
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=["revenue", "expense"], width=33, state='readonly')
            type_combo.grid(row=1, column=1, pady=5, padx=5)

            # Parent category (optional)
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.parent_category', default="Parent Category:")).grid(row=2, column=0, sticky='w', pady=5, padx=5)
            parent_var = tk.StringVar()
            parent_combo = ttk.Combobox(form_frame, textvariable=parent_var, width=33)
            parent_combo.grid(row=2, column=1, pady=5, padx=5)

            # Load parent categories
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT category_id, category_name FROM budget_categories WHERE is_active = 1 ORDER BY category_name")
                parents = cursor.fetchall()
                conn.close()
                parent_combo['values'] = ['None'] + [f"{p[0]} - {p[1]}" for p in parents]
                parent_combo.set('None')
            except Exception as e:
                print(f"Error loading parent categories: {e}")

            # Description
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.description', default="Description:")).grid(row=3, column=0, sticky='nw', pady=5, padx=5)
            desc_text = tk.Text(form_frame, height=6, width=35)
            desc_text.grid(row=3, column=1, pady=5, padx=5)

            def save_category():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.name_required', default="Name Required"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_enter_a_category_name', default="Please enter a category name"), parent=add_dialog)
                    return

                category_type = type_var.get()
                parent_str = parent_var.get()
                parent_id = None
                if parent_str and parent_str != 'None':
                    try:
                        parent_id = int(parent_str.split(' - ')[0])
                    except (ValueError, IndexError):
                        pass

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO budget_categories
                        (category_name, category_type, parent_category_id, is_active, created_at)
                        VALUES (?, ?, ?, 1, ?)
                    ''', (name, category_type, parent_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), f"Category '{name}' created successfully", parent=add_dialog)
                    add_dialog.destroy()
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to create category: {e}", parent=add_dialog)

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=15)
            ttk.Button(button_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.save', default="Save"), command=save_category).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.cancel', default="Cancel"), command=add_dialog.destroy).pack(side='left', padx=5)

        def edit_category():
            """Edit selected category"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.no_selection', default="No Selection"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_select_a_category_to_edit', default="Please select a category to edit"), parent=dialog)
                return

            values = tree.item(selection[0])['values']
            category_id = values[0]
            current_name = values[1]
            current_type = values[2]

            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"Edit Category - {category_id}")
            edit_dialog.geometry("500x350")
            edit_dialog.transient(dialog)
            edit_dialog.grab_set()

            form_frame = ttk.LabelFrame(edit_dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.category_details', default="Category Details"), padding=20)
            form_frame.pack(fill='both', expand=True, padx=20, pady=20)

            # Category ID (read-only)
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_id', default="Category ID:")).grid(row=0, column=0, sticky='w', pady=5, padx=5)
            ttk.Label(form_frame, text=category_id, foreground='blue').grid(row=0, column=1, sticky='w', pady=5, padx=5)

            # Category name
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_name', default="Category Name:")).grid(row=1, column=0, sticky='w', pady=5, padx=5)
            name_var = tk.StringVar(value=current_name)
            name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
            name_entry.grid(row=1, column=1, pady=5, padx=5)
            name_entry.focus()

            # Category type
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_type', default="Category Type:")).grid(row=2, column=0, sticky='w', pady=5, padx=5)
            type_var = tk.StringVar(value=current_type)
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=["revenue", "expense"], width=33, state='readonly')
            type_combo.grid(row=2, column=1, pady=5, padx=5)

            # Description
            ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.description', default="Description:")).grid(row=3, column=0, sticky='nw', pady=5, padx=5)
            desc_text = tk.Text(form_frame, height=5, width=35)
            desc_text.grid(row=3, column=1, pady=5, padx=5)

            def save_changes():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.name_required', default="Name Required"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_enter_a_category_name', default="Please enter a category name"), parent=edit_dialog)
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET category_name = ?, category_type = ?, updated_at = ?
                        WHERE category_id = ?
                    ''', (name, type_var.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), f"Category '{name}' updated successfully", parent=edit_dialog)
                    edit_dialog.destroy()
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to update category: {e}", parent=edit_dialog)

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=15)
            ttk.Button(button_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.save_changes', default="Save Changes"), command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.cancel', default="Cancel"), command=edit_dialog.destroy).pack(side='left', padx=5)

        def deactivate_category():
            """Deactivate selected category"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.no_selection', default="No Selection"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_select_a_category_to_deactivate', default="Please select a category to deactivate"), parent=dialog)
                return

            values = tree.item(selection[0])['values']
            category_id = values[0]
            category_name = values[1]

            if messagebox.askyesno(_t('gui.finance.finance.budget_manager.categories.dialogs.confirm_deactivation', default="Confirm Deactivation"),
                                  f"Deactivate category '{category_name}'?\n\nThis will hide the category but not delete it.",
                                  parent=dialog):
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET is_active = 0, updated_at = ?
                        WHERE category_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), f"Category '{category_name}' deactivated", parent=dialog)
                    refresh_categories()
                except Exception as e:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to deactivate category: {e}", parent=dialog)

        def refresh_categories():
            """Refresh category list"""
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Show active or all based on checkbox
                if show_inactive_var.get():
                    cursor.execute('''
                        SELECT bc.category_id, bc.category_name, bc.category_type,
                               COALESCE(pc.category_name, 'None') as parent_name,
                               CASE WHEN bc.is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                        FROM budget_categories bc
                        LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                        ORDER BY bc.category_type, bc.category_name
                    ''')
                else:
                    cursor.execute('''
                        SELECT bc.category_id, bc.category_name, bc.category_type,
                               COALESCE(pc.category_name, 'None') as parent_name,
                               'Active' as status
                        FROM budget_categories bc
                        LEFT JOIN budget_categories pc ON bc.parent_category_id = pc.category_id
                        WHERE bc.is_active = 1
                        ORDER BY bc.category_type, bc.category_name
                    ''')

                categories = cursor.fetchall()
                conn.close()

                for category in categories:
                    tree.insert('', 'end', values=tuple(category))

                status_label.config(text=f"Total categories: {len(categories)}")

            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to load categories: {e}", parent=dialog)

        # Toolbar buttons
        tk.Button(toolbar, text=_t('gui.finance.finance.budget_manager.categories.buttons.add_category', default="➕ Add Category"), command=add_category,
                 bg='#27ae60', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text=_t('gui.finance.finance.budget_manager.categories.buttons.edit_category', default="✏️ Edit Category"), command=edit_category,
                 bg='#f39c12', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text=_t('gui.finance.finance.budget_manager.categories.buttons.deactivate_variant_2', default="🗑️ Deactivate"), command=deactivate_category,
                 bg='#e74c3c', fg='white', padx=10).pack(side='left', padx=5)
        tk.Button(toolbar, text=_t('gui.finance.finance.budget_manager.categories.buttons.refresh', default="🔄 Refresh"), command=refresh_categories,
                 bg='#3498db', fg='white', padx=10).pack(side='left', padx=5)

        show_inactive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text=_t('gui.finance.finance.budget_manager.categories.buttons.show_inactive', default="Show Inactive"), variable=show_inactive_var,
                       command=refresh_categories).pack(side='left', padx=10)

        # Main content area
        content_frame = tk.Frame(dialog, bg='white')
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview
        tree_frame = tk.Frame(content_frame)
        tree_frame.pack(fill='both', expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side='right', fill='y')

        tree = ttk.Treeview(tree_frame,
                           columns=('id', 'name', 'type', 'parent', 'status'),
                           show='headings', yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=tree.yview)

        tree.heading('id', text=_t('gui.finance.finance.budget_manager.categories.headings.id', default='ID'))
        tree.heading('name', text=_t('gui.finance.finance.budget_manager.categories.headings.category_name', default='Category Name'))
        tree.heading('type', text=_t('gui.finance.finance.budget_manager.categories.headings.type', default='Type'))
        tree.heading('parent', text=_t('gui.finance.finance.budget_manager.categories.headings.parent_category', default='Parent Category'))
        tree.heading('status', text=_t('gui.finance.finance.budget_manager.categories.headings.status', default='Status'))

        tree.column('id', width=60)
        tree.column('name', width=250)
        tree.column('type', width=100)
        tree.column('parent', width=200)
        tree.column('status', width=100)

        tree.pack(fill='both', expand=True)

        # Status bar
        status_frame = tk.Frame(dialog, bg='#ecf0f1', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)

        status_label = tk.Label(status_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.loading_categories', default="Loading categories..."),
                               bg='#ecf0f1', anchor='w')
        status_label.pack(side='left', padx=10)

        ttk.Button(status_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.close', default="Close"), command=dialog.destroy).pack(side='right', padx=10, pady=3)

        # Initial load
        refresh_categories()

    def gui_edit_budget_category(self):
        """GUI wrapper for edit_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.edit_budget_category', default="Edit Budget Category"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.edit_category', default="Edit Category"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Category ID
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_id', default="Category ID:")).pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)

        # New name
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.new_name', default="New Name:")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # New description
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.new_description', default="New Description:")).pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def edit_category_action():
            try:
                category_id = int(category_id_var.get())
                new_name = name_var.get().strip()
                new_description = desc_text.get("1.0", tk.END).strip()

                if not category_id:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.category_id_is_required', default="Category ID is required"))
                    return

                edit_budget_category(category_id, new_name, new_description)
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.budget_category_updated_successfully', default="Budget category updated successfully!"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.invalid_category_id', default="Invalid Category ID"))
            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to edit budget category: {e}")

        ttk.Button(form_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.update_category', default="Update Category"), command=edit_category_action).pack(pady=20)

    def gui_deactivate_budget_category(self):
        """GUI wrapper for deactivate_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.deactivate_budget_category', default="Deactivate Budget Category"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.deactivate_category', default="Deactivate Category"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Category ID
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_id_to_deactivate', default="Category ID to Deactivate:")).pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)

        def deactivate_category_action():
            try:
                category_id = int(category_id_var.get())

                if messagebox.askyesno(_t('gui.finance.finance.budget_manager.categories.dialogs.confirm', default="Confirm"), f"Deactivate budget category {category_id}?"):
                    deactivate_budget_category(category_id)
                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.budget_category_deactivated_successfully', default="Budget category deactivated successfully!"))
                    dialog.destroy()

            except ValueError:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.invalid_category_id', default="Invalid Category ID"))
            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to deactivate budget category: {e}")

        ttk.Button(form_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.deactivate', default="Deactivate"), command=deactivate_category_action).pack(pady=20)

    def gui_activate_budget_category(self):
        """GUI wrapper for activate_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.activate_budget_category', default="Activate Budget Category"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.activate_category', default="Activate Category"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Category ID
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_id_to_activate', default="Category ID to Activate:")).pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)

        def activate_category_action():
            try:
                category_id = int(category_id_var.get())

                if messagebox.askyesno(_t('gui.finance.finance.budget_manager.categories.dialogs.confirm', default="Confirm"), f"Activate budget category {category_id}?"):
                    # Update database to set is_active = 1
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE budget_categories
                        SET is_active = 1, updated_at = ?
                        WHERE category_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), category_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.budget_category_activated_successfully', default="Budget category activated successfully!"))
                    dialog.destroy()
                    if hasattr(self, 'refresh_budget'):
                        self.refresh_budget()

            except ValueError:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.invalid_category_id', default="Invalid Category ID"))
            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to activate budget category: {e}")

        ttk.Button(form_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.activate', default="Activate"), command=activate_category_action).pack(pady=20)

    def gui_view_budget_categories(self):
        """GUI wrapper for view_budget_categories"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.view_budget_categories', default="View Budget Categories"))
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            view_budget_categories()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=80, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_t('gui.finance.finance.budget_manager.categories.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to view budget categories: {e}")

    def gui_create_budget_category(self):
        """GUI wrapper for create_budget_category"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.create_budget_category', default="Create Budget Category"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.category_details', default="Category Details"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Category name
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_name', default="Category Name:")).pack(anchor='w', pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var).pack(anchor='w', fill='x', pady=5)

        # Category type
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_type', default="Category Type:")).pack(anchor='w', pady=5)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                 values=["revenue", "expense"])
        type_combo.pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.description', default="Description:")).pack(anchor='w', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=50)
        desc_text.pack(anchor='w', fill='both', expand=True, pady=5)

        def create_category_action():
            try:
                name = name_var.get().strip()
                category_type = type_var.get().strip()
                description = desc_text.get("1.0", tk.END).strip()

                if not all([name, category_type]):
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.name_and_type_are_required', default="Name and type are required"))
                    return

                create_budget_category(name, category_type, description)
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.budget_category_created_successfully', default="Budget category created successfully!"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to create budget category: {e}")

        ttk.Button(form_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.create_category', default="Create Category"), command=create_category_action).pack(pady=20)

    def gui_update_actual_amounts(self):
        """GUI wrapper for update_actual_amounts"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.update_actual_amounts', default="Update Actual Amounts"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.actual_amount_update', default="Actual Amount Update"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Budget plan ID
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.budget_plan_id', default="Budget Plan ID:")).pack(anchor='w', pady=5)
        plan_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=plan_id_var).pack(anchor='w', fill='x', pady=5)

        # Category ID
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.category_id', default="Category ID:")).pack(anchor='w', pady=5)
        category_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=category_id_var).pack(anchor='w', fill='x', pady=5)

        # Actual amount
        ttk.Label(form_frame, text=_t('gui.finance.finance.budget_manager.categories.labels.actual_amount', default="Actual Amount:")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        def update_amounts_action():
            try:
                plan_id = int(plan_id_var.get())
                category_id = int(category_id_var.get())
                amount = float(amount_var.get())

                if not all([plan_id, category_id, amount >= 0]):
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.all_fields_are_required', default="All fields are required"))
                    return

                update_actual_amounts(plan_id, category_id, amount)
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.actual_amounts_updated_successfully', default="Actual amounts updated successfully!"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.invalid_id_or_amount_values', default="Invalid ID or amount values"))
            except Exception as e:
                messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to update actual amounts: {e}")

        ttk.Button(form_frame, text=_t('gui.finance.finance.budget_manager.categories.buttons.update_amounts', default="Update Amounts"), command=update_amounts_action).pack(pady=20)

    def add_budget_category(self):
        """Add category to selected budget"""
        if not hasattr(self, 'my_budgets_tree'):
            messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_navigate_to_my_budgets_tab_first', default="Please navigate to My Budgets tab first."))
            return

        selection = self.my_budgets_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.finance.finance.budget_manager.categories.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_select_a_budget_first', default="Please select a budget first."))
            return

        try:
            item = self.my_budgets_tree.item(selection[0])
            budget_id = item['values'][0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.finance.finance.budget_manager.categories.windows.add_budget_category', default="Add Budget Category"))
            dialog.geometry("400x250")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.category_name', default="Category Name:")).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            name_entry = ttk.Entry(dialog, width=30)
            name_entry.grid(row=0, column=1, padx=10, pady=10)

            ttk.Label(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.category_type', default="Category Type:")).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
            type_combo = ttk.Combobox(dialog,
                values=['essential', 'discretionary', 'savings', 'debt'],
                state='readonly', width=28)
            type_combo.current(0)
            type_combo.grid(row=1, column=1, padx=10, pady=10)

            ttk.Label(dialog, text=_t('gui.finance.finance.budget_manager.categories.labels.allocated_amount', default="Allocated Amount (\u00a3):")).grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
            amount_entry = ttk.Entry(dialog, width=30)
            amount_entry.grid(row=2, column=1, padx=10, pady=10)

            def save_category():
                try:
                    name = name_entry.get().strip()
                    cat_type = type_combo.get()
                    amount = float(amount_entry.get().strip())

                    if not name or amount <= 0:
                        messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.please_fill_all_fields', default="Please fill all fields."), parent=dialog)
                        return

                    from education_system.systems.university.infrastructure.database.db import transaction
                    with transaction() as conn:
                        conn.execute('''
                            INSERT INTO budget_categories
                            (budget_id, category_name, category_type, allocated_amount)
                            VALUES (?, ?, ?, ?)
                        ''', (budget_id, name, cat_type, amount))

                        conn.execute('''
                            UPDATE student_budgets
                            SET allocated_amount = allocated_amount + ?
                            WHERE budget_id = ?
                        ''', (amount, budget_id))

                    messagebox.showinfo(_t('gui.finance.finance.budget_manager.categories.dialogs.success', default="Success"), _t('gui.finance.finance.budget_manager.categories.dialogs.category_added_successfully', default="Category added successfully!"), parent=dialog)
                    dialog.destroy()
                    self.refresh_my_budgets()

                except ValueError:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), _t('gui.finance.finance.budget_manager.categories.dialogs.invalid_amount', default="Invalid amount."), parent=dialog)
                except Exception as e:
                    messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to add category: {e}", parent=dialog)

            ttk.Button(dialog, text=_t('gui.finance.finance.budget_manager.categories.buttons.save', default="Save"), command=save_category).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.categories.dialogs.error', default="Error"), f"Failed to open category dialog: {e}")
