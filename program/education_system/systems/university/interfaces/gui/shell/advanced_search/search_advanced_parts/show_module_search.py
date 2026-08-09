"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_module_search(self):
    """Complete module enrollment search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.module_enrollment_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.module_enrollment_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Module selection
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.select_modules')}:").pack(anchor='w')

    modules_frame = ttk.Frame(frame)
    modules_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    # Module listbox with scrollbar
    listbox_frame = ttk.Frame(modules_frame)
    listbox_frame.pack(fill=tk.BOTH, expand=True)

    self.module_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, height=10)
    scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.module_listbox.yview)
    self.module_listbox.configure(yscrollcommand=scrollbar.set)

    self.module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load modules
    self.load_available_modules()

    # Match type
    match_frame = ttk.Frame(frame)
    match_frame.pack(fill=tk.X, pady=(10, 20))

    ttk.Label(match_frame, text=f"{_t('advanced_search.search_advanced.match_type')}:").pack(anchor='w')
    match_var = tk.StringVar(value=_t('gui.shell.advanced_search.search_advanced_parts.show_module_search.values.any', default="any"))
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.any_selected_modules'), variable=match_var, value="any").pack(anchor='w')
    ttk.Radiobutton(match_frame, text=_t('advanced_search.search_advanced.all_selected_modules'), variable=match_var, value="all").pack(anchor='w')

    def execute_module_search():
        selected_indices = self.module_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning(_t('gui.shell.advanced_search.search_advanced_parts.show_module_search.dialogs.t_advanced_search_no_selection', default="_t('advanced_search.no_selection')"), _t('gui.shell.advanced_search.search_advanced_parts.show_module_search.dialogs.please_select_at_least_one_module', default="Please select at least one module."))
            return

        selected_modules = [self.available_modules[i][0] for i in selected_indices]
        match_type = match_var.get()

        dialog.destroy()
        self.update_status("Searching by module enrollment...")

        def run_module_search():
            try:
                results = self.perform_module_search(selected_modules, match_type)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Module search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Module search error: {str(e)}"))

        threading.Thread(target=run_module_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_module_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
