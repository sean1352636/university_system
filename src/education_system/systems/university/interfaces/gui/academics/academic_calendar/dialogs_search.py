import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.systems.university.infrastructure.i18n import get_text as _
from education_system.systems.university.interfaces.gui.academics.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class AdvancedSearchDialog:
    """Dialog for advanced search functionality with larger window and proper scrolling"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academics.calendar.advanced_search"))
        self.dialog.geometry("900x700")
        self.dialog.minsize(700, 500)
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academics.calendar.advanced_search"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text=_("academics.calendar.search_criteria"), padding=10)
        criteria_frame.pack(fill=tk.X, pady=(0, 15))

        # Text search
        ttk.Label(criteria_frame, text=_("academics.calendar.search_text")).pack(anchor=tk.W)
        self.text_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.text_var).pack(fill=tk.X, pady=(5, 15))

        # Date range
        date_frame = ttk.Frame(criteria_frame)
        date_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(date_frame, text=_("academics.calendar.start_date_label")).pack(side=tk.LEFT)
        self.start_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=15).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(date_frame, text=_("academics.calendar.end_date_label")).pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=15).pack(side=tk.LEFT, padx=(5, 0))

        # Event type and semester row
        type_frame = ttk.Frame(criteria_frame)
        type_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(type_frame, text=_("academics.calendar.event_type")).pack(side=tk.LEFT)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=self.type_var, width=20,
                                values=["", "Academic", "Holiday", "Administrative", "Social", "Sports", "Trip", "Deadline", "Finance", "Library"])
        type_combo.pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(type_frame, text=_("academics.calendar.semester")).pack(side=tk.LEFT)
        self.semester_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.semester_var, width=20).pack(side=tk.LEFT, padx=(5, 0))

        # Tags
        ttk.Label(criteria_frame, text=_("academics.calendar.tags_label")).pack(anchor=tk.W)
        self.tags_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.tags_var).pack(fill=tk.X, pady=(5, 0))

        # Results frame with proper scrollbar layout
        results_frame = ttk.LabelFrame(main_frame, text=_("academics.calendar.search_results"), padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        # Create a container for treeview and scrollbars
        tree_container = ttk.Frame(results_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        # Results tree with more columns
        self.results_tree = ttk.Treeview(tree_container,
                                       columns=('Date', 'End Date', 'Type', 'Description'),
                                       show='tree headings',
                                       height=15)

        # Configure columns
        self.results_tree.heading('#0', text=_("academics.calendar.columns.event_name"))
        self.results_tree.heading('Date', text=_("academics.calendar.columns.start_date"))
        self.results_tree.heading('End Date', text=_("academics.calendar.columns.end_date"))
        self.results_tree.heading('Type', text=_("academics.calendar.columns.type"))
        self.results_tree.heading('Description', text=_("academics.calendar.columns.description"))

        self.results_tree.column('#0', width=200, minwidth=150)
        self.results_tree.column('Date', width=100, minwidth=80)
        self.results_tree.column('End Date', width=100, minwidth=80)
        self.results_tree.column('Type', width=100, minwidth=80)
        self.results_tree.column('Description', width=350, minwidth=200)

        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.results_tree.yview)
        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.results_tree.xview)

        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid layout for proper scrollbar positioning
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        # Result count label
        self.result_count_label = ttk.Label(results_frame, text="")
        self.result_count_label.pack(anchor=tk.W, pady=(10, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        ttk.Button(button_frame, text=_("common.search"), command=self._perform_search).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_("common.clear"), command=self._clear_search).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academics.calendar.export_results"), command=self._export_results).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.close"), command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _perform_search(self):
        """Perform the search"""
        try:
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)

            # Build search criteria
            criteria = {}

            text = self.text_var.get().strip()
            if text:
                criteria['text'] = text

            start_date = self.start_date_var.get().strip()
            if start_date:
                criteria['start_date'] = start_date

            end_date = self.end_date_var.get().strip()
            if end_date:
                criteria['end_date'] = end_date

            event_type = self.type_var.get().strip()
            if event_type:
                criteria['event_type'] = event_type

            tags = self.tags_var.get().strip()
            if tags:
                criteria['tags'] = [tag.strip() for tag in tags.split(',') if tag.strip()]

            # Perform search
            success, results = self.calendar_manager.search.advanced_search(criteria)

            if success:
                self.search_results = results  # Store for export
                for event in results:
                    event_date = event.get('date') or event.get('date_start', '')
                    end_date = event.get('date_end', '')
                    description = (event.get('description', '') or '')[:80]
                    if len(event.get('description', '') or '') > 80:
                        description += "..."

                    self.results_tree.insert('', 'end',
                                           text=event['name'],
                                           values=(event_date, end_date, event['event_type'], description))

                self.result_count_label.config(text=_("academics.calendar.found_events", count=len(results)))
            else:
                self.result_count_label.config(text=_("academics.calendar.search_failed"))
                messagebox.showerror(_("common.error"), _("academics.calendar.search_failed_detail", error=results), parent=self.dialog)

        except Exception as e:
            self.result_count_label.config(text=_("academics.calendar.search_error"))
            messagebox.showerror(_("common.error"), _("academics.calendar.search_failed_detail", error=str(e)), parent=self.dialog)

    def _clear_search(self):
        """Clear search criteria and results"""
        self.text_var.set("")
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.type_var.set("")
        self.semester_var.set("")
        self.tags_var.set("")
        self.result_count_label.config(text="")
        self.search_results = []

        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

    def _export_results(self):
        """Export search results to file"""
        if not hasattr(self, 'search_results') or not self.search_results:
            messagebox.showwarning(_("academics.calendar.no_results"), _("academics.calendar.no_results_to_export"), parent=self.dialog)
            return

        filename = filedialog.asksaveasfilename(
            title=_("academics.calendar.export_search_results"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self.dialog
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    if filename.endswith('.csv'):
                        f.write("Event Name,Start Date,End Date,Type,Description\n")
                        for event in self.search_results:
                            name = event.get('name', '').replace(',', ';')
                            date = event.get('date') or event.get('date_start', '')
                            end_date = event.get('date_end', '')
                            etype = event.get('event_type', '')
                            desc = (event.get('description', '') or '').replace(',', ';').replace('\n', ' ')
                            f.write(f"{name},{date},{end_date},{etype},{desc}\n")
                    else:
                        f.write("SEARCH RESULTS EXPORT\n")
                        f.write("=" * 60 + "\n\n")
                        for event in self.search_results:
                            f.write(f"Event: {event.get('name', '')}\n")
                            f.write(f"Date: {event.get('date') or event.get('date_start', '')}\n")
                            if event.get('date_end'):
                                f.write(f"End Date: {event.get('date_end')}\n")
                            f.write(f"Type: {event.get('event_type', '')}\n")
                            if event.get('description'):
                                f.write(f"Description: {event.get('description')}\n")
                            f.write("-" * 40 + "\n\n")
                        f.write(f"\nTotal: {len(self.search_results)} event(s)\n")

                messagebox.showinfo(_("academics.calendar.export_complete"), _("academics.calendar.results_exported", filename=filename), parent=self.dialog)
            except Exception as e:
                messagebox.showerror(_("academics.calendar.export_error"), _("academics.calendar.export_failed", error=str(e)), parent=self.dialog)

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


