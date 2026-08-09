"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def mark_for_followup(self):
    """Mark students for follow-up"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_available"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"📌 {_t('advanced_search.mark_followup_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.mark_followup_title", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.followup_reason")).pack(anchor='w')
    reason_var = tk.StringVar()
    ttk.Entry(frame, textvariable=reason_var, width=40).pack(fill=tk.X, pady=(0, 20))

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.priority_label")).pack(anchor='w')
    priority_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.mark_for_followup.values.medium', default="medium"))

    priorities = [(_t("advanced_search.bulk_operations.priority_high"), "high"), (_t("advanced_search.bulk_operations.priority_medium"), "medium"), (_t("advanced_search.bulk_operations.priority_low"), "low")]
    for text, value in priorities:
        ttk.Radiobutton(frame, text=text, variable=priority_var, value=value).pack(anchor='w')

    def mark_students():
        reason = reason_var.get().strip()
        if not reason:
            messagebox.showwarning(_t("advanced_search.bulk_operations.missing_reason_title"), _t("advanced_search.bulk_operations.missing_reason_msg"))
            return

        priority = priority_var.get()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create follow-up data
        followup_data = {
            'reason': reason,
            'priority': priority,
            'marked_date': timestamp,
            'marked_by': 'current_user',
            'students': [
                {
                    'student_id': s[0],
                    'name': f"{s[3]} {s[5]}",
                    'email': s[1]
                } for s in self.search_results
            ]
        }

        # Save to file
        filename = f"followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(followup_data, f, indent=2)

        messagebox.showinfo(_t("advanced_search.bulk_operations.followup_marked_title"),
                          _t("advanced_search.bulk_operations.followup_marked_msg",
                             count=len(self.search_results), reason=reason, priority=priority, filename=filename))
        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"📌 {_t('advanced_search.bulk_operations.mark_btn')}", command=mark_students).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
