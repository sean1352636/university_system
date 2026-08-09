"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_search_all_fields(self):
    """Show search all fields dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.search_all_fields_dialog_title')}")
    dialog.geometry("400x250")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.search_all_fields_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.search_term')}:").pack(anchor='w')
    search_var = tk.StringVar()
    ttk.Entry(frame, textvariable=search_var, width=40).pack(fill=tk.X, pady=(0, 20))

    ttk.Label(frame, text=_t('advanced_search.search_advanced.search_all_fields_info'),
             font=('Arial', 9)).pack(pady=(0, 20))

    def execute_all_fields_search():
        search_term = search_var.get().strip()

        if not search_term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_term'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Searching all fields...")
        self.start_progress()

        def run_all_fields():
            try:
                results = self.perform_search_all_fields(search_term)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"All fields search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"All fields search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_all_fields, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_all_fields_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
