"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_regex_search(self):
    """Show regex search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.regex_search_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.regex_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.regex_pattern')}:").pack(anchor='w')
    pattern_var = tk.StringVar()
    ttk.Entry(frame, textvariable=pattern_var, width=50).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_field')}:").pack(anchor='w')
    field_var = tk.StringVar(value=_t('gui.shell.advanced_search.search_advanced_parts.show_regex_search.values.first_name', default="first_name"))
    field_combo = ttk.Combobox(frame, textvariable=field_var,
                              values=["first_name", "last_name", "email", "student_id"],
                              state='readonly')
    field_combo.pack(anchor='w', pady=(0, 20))

    # Pattern examples
    examples_frame = ttk.LabelFrame(frame, text=_t('advanced_search.search_advanced.pattern_examples'), padding="10")
    examples_frame.pack(fill=tk.X, pady=(0, 20))

    examples = [
        ("^J.*", "Names starting with 'J'"),
        (".*son$", "Names ending with 'son'"),
        ("[0-9]+", "Contains numbers"),
        ("^STU[0-9]{3}$", "Student ID format STU followed by 3 digits")
    ]

    for pattern, description in examples:
        example_frame = ttk.Frame(examples_frame)
        example_frame.pack(fill=tk.X, pady=2)
        ttk.Button(example_frame, text=pattern, width=15,
                  command=lambda p=pattern: pattern_var.set(p)).pack(side=tk.LEFT)
        ttk.Label(example_frame, text=f" - {description}").pack(side=tk.LEFT)

    def execute_regex_search():
        pattern = pattern_var.get().strip()
        field = field_var.get()

        if not pattern:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_pattern'), _t('advanced_search.search_advanced.enter_regex_pattern'))
            return

        dialog.destroy()
        self.update_status("Performing regex search...")
        self.start_progress()

        def run_regex():
            try:
                results = self.perform_regex_search(pattern, field)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Regex search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Regex search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_regex, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_regex_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
