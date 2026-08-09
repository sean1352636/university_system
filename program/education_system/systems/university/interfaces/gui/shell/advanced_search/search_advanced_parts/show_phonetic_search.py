"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_phonetic_search(self):
    """Show phonetic search dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔊 {_t('advanced_search.phonetic_search_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.phonetic_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.enter_name_phonetic')}:").pack(anchor='w')
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=30).pack(fill=tk.X, pady=(0, 20))

    info_text = """Phonetic search finds names that sound similar:
• John ↔ Jon
• Smith ↔ Smyth
• Catherine ↔ Katherine

Uses Soundex algorithm for matching."""

    ttk.Label(frame, text=info_text, font=('Arial', 9), justify=tk.LEFT).pack(pady=(0, 20))

    def execute_phonetic_search():
        name = name_var.get().strip()

        if not name:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_name'), _t('advanced_search.search_advanced.enter_name'))
            return

        dialog.destroy()
        self.update_status("Performing phonetic search...")
        self.start_progress()

        def run_phonetic():
            try:
                results = self.perform_phonetic_search(name)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Phonetic search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Phonetic search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_phonetic, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_phonetic_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
