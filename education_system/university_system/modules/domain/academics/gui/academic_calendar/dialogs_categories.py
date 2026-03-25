import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from education_system.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class EventCategoriesDialog:
    """Dialog for managing event categories"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.categories.dialog_title"))
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_categories()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.categories.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Notebook for categories and tags
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Categories tab
        categories_frame = ttk.Frame(notebook, padding=10)
        notebook.add(categories_frame, text=_("academic_calendar.categories.tab_categories"))

        # Action buttons for categories
        cat_action_frame = ttk.Frame(categories_frame)
        cat_action_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(cat_action_frame, text=_("academic_calendar.categories.add_category"),
                  command=self._add_category).pack(side=tk.LEFT, padx=5)
        ttk.Button(cat_action_frame, text=_("common.refresh"),
                  command=self._load_categories).pack(side=tk.RIGHT, padx=5)

        # Categories tree
        self.categories_tree = ttk.Treeview(categories_frame,
                                          columns=('Color', 'Description'),
                                          show='tree headings')
        self.categories_tree.pack(fill=tk.BOTH, expand=True)

        self.categories_tree.heading('#0', text=_("academic_calendar.categories.column_name"))
        self.categories_tree.heading('Color', text=_("academic_calendar.categories.column_color"))
        self.categories_tree.heading('Description', text=_("common.description"))

        # Tags tab
        tags_frame = ttk.Frame(notebook, padding=10)
        notebook.add(tags_frame, text=_("academic_calendar.categories.tab_tags"))

        # Action buttons for tags
        tag_action_frame = ttk.Frame(tags_frame)
        tag_action_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(tag_action_frame, text=_("academic_calendar.categories.add_tag"),
                  command=self._add_tag).pack(side=tk.LEFT, padx=5)
        ttk.Button(tag_action_frame, text=_("academic_calendar.categories.assign_to_event"),
                  command=self._assign_tag).pack(side=tk.LEFT, padx=5)
        
        # Tags listbox
        self.tags_listbox = tk.Listbox(tags_frame)
        self.tags_listbox.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_categories(self):
        """Load categories into tree"""
        try:
            # Clear existing items
            for item in self.categories_tree.get_children():
                self.categories_tree.delete(item)
            
            # Get categories from database
            categories = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM event_categories ORDER BY name"
            )
            
            for category in categories:
                self.categories_tree.insert('', 'end',
                                          text=category['name'],
                                          values=(category['color_code'] or 'N/A',
                                                category['description'] or ''))
            
            # Load tags
            self.tags_listbox.delete(0, tk.END)
            tags = self.calendar_manager.db_manager.execute_query(
                "SELECT name FROM event_tags ORDER BY name"
            )
            for tag in tags:
                self.tags_listbox.insert(tk.END, tag['name'])
                
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.categories.load_failed", error=e))
    
    def _add_category(self):
        """Add new category"""
        AddCategoryDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _add_tag(self):
        """Add new tag"""
        AddTagDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _assign_tag(self):
        """Assign tag to event"""
        AssignTagDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddCategoryDialog:
    """Simple dialog for adding categories"""

    def __init__(self, parent, calendar_manager, callback=None):
        name = simpledialog.askstring(_("academic_calendar.categories.add_category"), _("academic_calendar.categories.category_name_prompt"))
        if not name:
            return

        color = simpledialog.askstring(_("academic_calendar.categories.add_category"), _("academic_calendar.categories.color_code_prompt")) or None
        description = simpledialog.askstring(_("academic_calendar.categories.add_category"), _("academic_calendar.categories.description_prompt")) or None

        try:
            success, message = calendar_manager.categories.create_category(name, color, description)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if callback:
                    callback()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.categories.add_category_failed", error=e))


class AddTagDialog:
    """Simple dialog for adding tags"""

    def __init__(self, parent, calendar_manager, callback=None):
        name = simpledialog.askstring(_("academic_calendar.categories.add_tag"), _("academic_calendar.categories.tag_name_prompt"))
        if not name:
            return

        color = simpledialog.askstring(_("academic_calendar.categories.add_tag"), _("academic_calendar.categories.color_code_prompt")) or None

        try:
            success, message = calendar_manager.categories.create_tag(name, color)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if callback:
                    callback()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.categories.add_tag_failed", error=e))


class AssignTagDialog:
    """Dialog for assigning tags to events — shows a dropdown of existing events."""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        # Load existing events for the dropdown
        self.event_map = {}
        try:
            rows = calendar_manager.db_manager.execute_query(
                "SELECT id, name FROM academic_calendar_events ORDER BY name"
            )
            for row in rows:
                label = f"{row['name']} ({row['id'][:8]}...)"
                self.event_map[label] = row['id']
        except Exception:
            pass

        if not self.event_map:
            messagebox.showwarning(_("common.warning"), "No events found. Create an event first.")
            return

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.categories.assign_tag"))
        self.dialog.geometry("450x200")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog)

        frm = ttk.Frame(self.dialog, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Event:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_combo = ttk.Combobox(frm, values=list(self.event_map.keys()), width=45, state='readonly')
        self.event_combo.grid(row=0, column=1, pady=5, padx=5)
        if self.event_map:
            self.event_combo.current(0)

        ttk.Label(frm, text="Tags (comma-separated):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.tags_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.tags_var, width=47).grid(row=1, column=1, pady=5, padx=5)

        ttk.Button(frm, text="Assign Tags", command=self._assign).grid(row=2, column=1, sticky=tk.E, pady=15)

    def _assign(self):
        selected = self.event_combo.get()
        if selected not in self.event_map:
            messagebox.showwarning(_("common.warning"), "Please select an event.")
            return

        tags_text = self.tags_var.get().strip()
        if not tags_text:
            messagebox.showwarning(_("common.warning"), "Please enter at least one tag.")
            return

        event_id = self.event_map[selected]
        tag_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]

        try:
            success, message = self.calendar_manager.categories.assign_tags_to_event(event_id, tag_list)
            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.categories.assign_tags_failed", error=e))


