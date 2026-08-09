"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_wildcard_search(self):
    """Show wildcard search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🃏 {_t('advanced_search.wildcard_search_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.wildcard_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.wildcard_pattern_label')}:").pack(anchor='w')
    pattern_var = tk.StringVar()
    ttk.Entry(frame, textvariable=pattern_var, width=40).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_field')}:").pack(anchor='w')
    field_var = tk.StringVar(value=_t('gui.shell.advanced_search.search_advanced_parts.show_wildcard_search.values.first_name', default="first_name"))
    field_combo = ttk.Combobox(frame, textvariable=field_var,
                              values=["first_name", "last_name", "email", "student_id"],
                              state='readonly')
    field_combo.pack(anchor='w', pady=(0, 20))

    # Examples
    examples_frame = ttk.LabelFrame(frame, text=_t('advanced_search.search_advanced.examples'), padding="10")
    examples_frame.pack(fill=tk.X, pady=(0, 20))

    examples = ["J*", "*son", "STU???", "*@*.com"]
    for example in examples:
        ttk.Button(examples_frame, text=example, width=10,
                  command=lambda p=example: pattern_var.set(p)).pack(side=tk.LEFT, padx=2)

    def execute_wildcard_search():
        pattern = pattern_var.get().strip()
        field = field_var.get()

        if not pattern:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_pattern'), _t('advanced_search.search_advanced.missing_wildcard_pattern'))
            return

        dialog.destroy()
        self.update_status("Performing wildcard search...")
        self.start_progress()

        def run_wildcard():
            try:
                results = self.perform_wildcard_search(pattern, field)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Wildcard search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Wildcard search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_wildcard, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_wildcard_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
