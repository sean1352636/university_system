"""Template dialogs for the data backup GUI.

Provides the TemplateSelectionDialog for choosing backup templates and the
TemplateManagerDialog for managing (loading, deleting, renaming) templates.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import json
from pathlib import Path

from university_system.modules.shared.gui.database.config import config, save_config
from university_system.modules.shared.gui.database.shared_imports import logger
from university_system.modules.shared.gui.database.operations.template_ops import list_backup_templates, load_backup_template


class TemplateSelectionDialog:
    """Dialog for selecting templates with descriptions"""

    def __init__(self, parent, template_names, template_data=None):
        self.selected_template = None
        self.template_data = template_data or {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Backup Template")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Template list
        list_frame = ttk.LabelFrame(self.dialog, text="Available Templates", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.template_var = tk.StringVar()

        # Add radio buttons with descriptions
        for template_name in template_names:
            frame = ttk.Frame(list_frame)
            frame.pack(fill="x", pady=2)

            ttk.Radiobutton(frame, text=template_name, variable=self.template_var,
                           value=template_name).pack(anchor="w")

            # Show description if available
            if template_name in self.template_data:
                desc = self.template_data[template_name].get("description", "")
                source = self.template_data[template_name].get("source", "")
                source_text = f" [{source}]" if source else ""
                if desc:
                    ttk.Label(frame, text=f"  {desc}{source_text}",
                             font=("TkDefaultFont", 8), foreground="gray").pack(anchor="w", padx=20)

        if template_names:
            self.template_var.set(template_names[0])

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Load", command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")

        parent.wait_window(self.dialog)

    def ok(self):
        """OK button handler"""
        self.selected_template = self.template_var.get()
        self.dialog.destroy()

    def cancel(self):
        """Cancel button handler"""
        self.selected_template = None
        self.dialog.destroy()


class TemplateManagerDialog:
    """Dialog for managing backup templates"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_templates()

    def create_widgets(self):
        """Create dialog widgets"""
        # Template list
        list_frame = ttk.LabelFrame(self.dialog, text="Templates", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill="both", expand=True)

        self.template_listbox = tk.Listbox(listbox_frame)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.template_listbox.yview)
        self.template_listbox.configure(yscrollcommand=scrollbar.set)

        self.template_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.template_listbox.bind("<<ListboxSelect>>", self.show_template_details)

        # Template details
        details_frame = ttk.LabelFrame(self.dialog, text="Template Details", padding=10)
        details_frame.pack(fill="x", padx=10, pady=5)

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill="both", expand=True)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Load Template", command=self.load_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Delete Template", command=self.delete_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Rename Template", command=self.rename_template).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def load_templates(self):
        """Load template list from JSON files and config"""
        self.template_listbox.delete(0, tk.END)
        # Use new list_backup_templates function
        self.templates = list_backup_templates()

        for template_name in self.templates.keys():
            self.template_listbox.insert(tk.END, template_name)

    def show_template_details(self, event=None):
        """Show details for selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            return

        template_name = self.template_listbox.get(selection[0])
        template_info = self.templates.get(template_name, {})

        details = f"Template: {template_name}\n"
        details += "=" * 40 + "\n\n"

        # Show description and source
        details += f"Description: {template_info.get('description', 'N/A')}\n"
        details += f"Source: {template_info.get('source', 'N/A')}\n"
        if 'path' in template_info:
            details += f"Path: {template_info['path']}\n"
        details += "\n"

        # Try to load full template data
        try:
            if template_info.get('source') == 'file':
                template_file = Path(template_info['path'])
                with open(template_file, 'r') as f:
                    template_data = json.load(f)
            else:
                template_data = config.get("backup_templates", {}).get(template_name, {})

            # Show key settings
            key_settings = [
                "backup_type", "backup_frequency", "scheduled_backup_time",
                "max_backups", "auto_backup_enabled", "encryption_enabled",
                "compression_enabled", "compression_format", "cloud_enabled",
                "remote_enabled", "email_notifications"
            ]

            details += "Settings:\n"
            details += "-" * 40 + "\n"
            for key in key_settings:
                if key in template_data:
                    details += f"{key.replace('_', ' ').title()}: {template_data[key]}\n"

        except Exception as e:
            details += f"\nError loading template details: {e}\n"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def load_template(self):
        """Load selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to load")
            return

        template_name = self.template_listbox.get(selection[0])

        if messagebox.askyesno("Load Template", f"Load template '{template_name}'?\n\nThis will overwrite current settings."):
            if load_backup_template(template_name):
                messagebox.showinfo("Success", f"Template '{template_name}' loaded successfully!")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to load template")

    def delete_template(self):
        """Delete selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return

        template_name = self.template_listbox.get(selection[0])

        if messagebox.askyesno("Delete Template", f"Are you sure you want to delete template '{template_name}'?"):
            try:
                del config["backup_templates"][template_name]
                save_config()
                self.load_templates()
                self.details_text.delete(1.0, tk.END)
                messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {e}")

    def rename_template(self):
        """Rename selected template"""
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to rename")
            return

        old_name = self.template_listbox.get(selection[0])
        new_name = tk.simpledialog.askstring("Rename Template", f"Enter new name for '{old_name}':")

        if new_name and new_name != old_name:
            if new_name in self.templates:
                messagebox.showerror("Error", "Template with that name already exists")
                return

            try:
                config["backup_templates"][new_name] = config["backup_templates"][old_name]
                del config["backup_templates"][old_name]
                save_config()
                self.load_templates()
                messagebox.showinfo("Success", f"Template renamed to '{new_name}'")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename template: {e}")
