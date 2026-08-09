"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_fuzzy_search(self):
    """Complete fuzzy search implementation"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_t('advanced_search.fuzzy_search_dialog_title'))
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.fuzzy_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_term')}:").pack(anchor='w')
    search_var = tk.StringVar()
    ttk.Entry(frame, textvariable=search_var, width=30).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.similarity_threshold')}:").pack(anchor='w')
    threshold_var = tk.StringVar(value="0.6")
    ttk.Entry(frame, textvariable=threshold_var, width=10).pack(anchor='w', pady=(0, 10))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.algorithm')}:").pack(anchor='w')
    algo_var = tk.StringVar(value="1")
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.standard_fuzzy_matching'), variable=algo_var, value="1").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.phonetic_matching_soundex'), variable=algo_var, value="2").pack(anchor='w')
    ttk.Radiobutton(frame, text=_t('advanced_search.search_advanced.both_algorithms'), variable=algo_var, value="3").pack(anchor='w', pady=(0, 20))

    def execute_fuzzy_search():
        term = search_var.get().strip()
        if not term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_input'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Performing fuzzy search...")

        def run_fuzzy():
            try:
                results = self.perform_fuzzy_search(term, float(threshold_var.get()), algo_var.get())
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Fuzzy search for '{term}' completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Fuzzy search error: {str(e)}"))

        threading.Thread(target=run_fuzzy, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t('advanced_search.search_advanced.search'), command=execute_fuzzy_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=dialog.destroy).pack(side=tk.RIGHT)
