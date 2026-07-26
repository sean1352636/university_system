"""Base GUI classes for tkinter module windows and dialogs.

Improvement #2: Deduplicate GUI Patterns
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


class BaseModuleGUI(tk.Frame):
    """Base class for module GUI frames with notebook layout.

    Usage:
        class StudentGUI(BaseModuleGUI):
            MODULE_TITLE = "Student Management"

            def __init__(self, parent, **kwargs):
                super().__init__(parent, **kwargs)
                self.add_tab("Students", self._build_students_tab)
    """

    MODULE_TITLE: str = "Module"

    def __init__(self, parent, user_info: dict | None = None, role: str | None = None,
                 db_path: str | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.user_info = user_info or {}
        self.role = role or "student"
        self.db_path = db_path

        self.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=self.MODULE_TITLE, font=("Helvetica", 14, "bold"),
                 fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=15)

        # Search
        search_frame = tk.Frame(header, bg="#2c3e50")
        search_frame.pack(side=tk.RIGHT, padx=10)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        tk.Button(search_frame, text="Search", command=self.on_search).pack(side=tk.LEFT)

        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor=tk.W,
                 relief=tk.SUNKEN, padx=10, font=("Helvetica", 9)).pack(fill=tk.X, side=tk.BOTTOM)

    def add_tab(self, title: str, build_func=None) -> tk.Frame:
        tab = tk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        if build_func:
            build_func(tab)
        return tab

    def set_status(self, message: str):
        self.status_var.set(message)

    def on_search(self):
        pass  # Override in subclass

    def show_error(self, title: str, message: str):
        messagebox.showerror(title, message)

    def show_info(self, title: str, message: str):
        messagebox.showinfo(title, message)

    def confirm(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def create_treeview(self, parent: tk.Frame, columns: list[tuple[str, str, int]], **kw) -> ttk.Treeview:
        frame = tk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        col_ids = [c[0] for c in columns]
        tree = ttk.Treeview(frame, columns=col_ids, show="headings", **kw)
        for col_id, heading, width in columns:
            tree.heading(col_id, text=heading)
            tree.column(col_id, width=width, minwidth=50)
        v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=v_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return tree

    def create_button_bar(self, parent: tk.Frame, buttons: list[tuple[str, callable]]) -> tk.Frame:
        bar = tk.Frame(parent)
        bar.pack(fill=tk.X, padx=5, pady=5)
        for label, callback in buttons:
            tk.Button(bar, text=label, command=callback, padx=10).pack(side=tk.LEFT, padx=3)
        return bar

    def is_admin(self) -> bool:
        return self.role in ("admin", "superadmin")


class BaseCRUDDialog(tk.Toplevel):
    """Base class for Create/Edit dialogs.

    Usage:
        class StudentDialog(BaseCRUDDialog):
            TITLE = "Student"
            FIELDS = [
                ("first_name", "First Name", "entry"),
                ("year_group", "Year Group", "combo", ["12", "13"]),
            ]
    """

    TITLE: str = "Record"
    FIELDS: list[tuple] = []

    def __init__(self, parent, record: dict | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.title(f"{'Edit' if record else 'Add'} {self.TITLE}")
        self.result: dict | None = None
        self.record = record or {}
        self._widgets = {}
        self.transient(parent)
        self.grab_set()
        self._build_form()
        self._build_buttons()
        self._center_on_parent(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_form(self):
        form = tk.Frame(self, padx=15, pady=10)
        form.pack(fill=tk.BOTH, expand=True)
        for i, field_def in enumerate(self.FIELDS):
            field_name, label = field_def[0], field_def[1]
            field_type = field_def[2] if len(field_def) > 2 else "entry"
            options = field_def[3] if len(field_def) > 3 else []
            tk.Label(form, text=f"{label}:", anchor=tk.W).grid(row=i, column=0, sticky=tk.W, pady=3)
            if field_type == "entry":
                var = tk.StringVar(value=self.record.get(field_name, ""))
                tk.Entry(form, textvariable=var, width=35).grid(row=i, column=1, sticky=tk.EW, pady=3)
                self._widgets[field_name] = var
            elif field_type == "combo":
                var = tk.StringVar(value=self.record.get(field_name, ""))
                ttk.Combobox(form, textvariable=var, values=options, width=33).grid(row=i, column=1, sticky=tk.EW, pady=3)
                self._widgets[field_name] = var
            elif field_type == "text":
                w = tk.Text(form, width=35, height=4)
                w.insert("1.0", self.record.get(field_name, ""))
                w.grid(row=i, column=1, sticky=tk.EW, pady=3)
                self._widgets[field_name] = w
            elif field_type == "check":
                var = tk.BooleanVar(value=bool(self.record.get(field_name, False)))
                tk.Checkbutton(form, variable=var).grid(row=i, column=1, sticky=tk.W, pady=3)
                self._widgets[field_name] = var
        form.grid_columnconfigure(1, weight=1)

    def _build_buttons(self):
        f = tk.Frame(self, padx=15, pady=10)
        f.pack(fill=tk.X)
        tk.Button(f, text="Cancel", command=self._on_cancel, width=10).pack(side=tk.RIGHT, padx=5)
        tk.Button(f, text="Save", command=self._on_save, width=10).pack(side=tk.RIGHT, padx=5)

    def _on_save(self):
        data = {}
        for name, widget in self._widgets.items():
            if isinstance(widget, (tk.StringVar, tk.BooleanVar)):
                data[name] = widget.get()
            elif isinstance(widget, tk.Text):
                data[name] = widget.get("1.0", tk.END).strip()
        error = self.validate(data)
        if error:
            messagebox.showerror("Validation Error", error)
            return
        self.result = data
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _center_on_parent(self, parent):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def validate(self, data: dict) -> str | None:
        """Override to add validation. Return error message or None."""
        return None
