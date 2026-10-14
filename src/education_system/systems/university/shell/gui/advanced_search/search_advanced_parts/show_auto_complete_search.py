"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_auto_complete_search(self):
    """Show auto-complete search interface"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔍 {_t('advanced_search.auto_complete_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('advanced_search.search_advanced.autocomplete_search_title'), style='Title.TLabel').pack(pady=(0, 20))

    # Search field with suggestions
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.type_to_search')}:").pack(anchor='w')

    search_var = tk.StringVar()
    search_entry = ttk.Entry(frame, textvariable=search_var, width=40)
    search_entry.pack(fill=tk.X, pady=(0, 10))

    # Suggestions listbox
    ttk.Label(frame, text=f"{_t('advanced_search.search_advanced.suggestions')}:").pack(anchor='w')

    suggestions_frame = ttk.Frame(frame)
    suggestions_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

    suggestions_listbox = tk.Listbox(suggestions_frame, height=10)
    suggestions_scrollbar = ttk.Scrollbar(suggestions_frame, orient=tk.VERTICAL, command=suggestions_listbox.yview)
    suggestions_listbox.configure(yscrollcommand=suggestions_scrollbar.set)

    suggestions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    suggestions_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_suggestions(*args):
        """Update suggestions based on input"""
        term = search_var.get().lower()
        suggestions_listbox.delete(0, tk.END)

        if len(term) >= 2:
            # Get suggestions from database
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get matching names, emails, and student IDs
                cursor.execute("""
                    SELECT DISTINCT
                        first_name || ' ' || last_name as full_name,
                        email_address,
                        student_id
                    FROM students
                    WHERE LOWER(first_name || ' ' || last_name) LIKE ?
                       OR LOWER(email_address) LIKE ?
                       OR LOWER(student_id) LIKE ?
                    LIMIT 20
                """, (f'%{term}%', f'%{term}%', f'%{term}%'))

                results = cursor.fetchall()
                conn.close()

                for full_name, email, student_id in results:
                    suggestions_listbox.insert(tk.END, f"{full_name} ({email})")

            except Exception as e:
                suggestions_listbox.insert(tk.END, f"Error loading suggestions: {str(e)}")

    search_var.trace('w', update_suggestions)

    def select_suggestion(event):
        """Select suggestion and populate search field"""
        selection = suggestions_listbox.curselection()
        if selection:
            selected_text = suggestions_listbox.get(selection[0])
            # Extract name from "Name (email)" format
            name_part = selected_text.split(' (')[0]
            search_var.set(name_part)

    suggestions_listbox.bind('<Double-1>', select_suggestion)

    def execute_autocomplete_search():
        term = search_var.get().strip()
        if not term:
            messagebox.showwarning(_t('advanced_search.search_advanced.missing_input'), _t('advanced_search.search_advanced.enter_search_term'))
            return

        dialog.destroy()
        self.update_status("Performing auto-complete search...")
        self.start_progress()

        def run_search():
            try:
                results = self.perform_autocomplete_search(term)
                self.output_queue.put(("search_results", results))
                self.output_queue.put(("log", f"Auto-complete search completed. Found {len(results)} results."))
            except Exception as e:
                self.output_queue.put(("error", f"Auto-complete search error: {str(e)}"))
            finally:
                self.output_queue.put(("stop_progress", None))

        threading.Thread(target=run_search, daemon=True).start()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"🔍 {_t('advanced_search.search_button')}", command=execute_autocomplete_search).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
