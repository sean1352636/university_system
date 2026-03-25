# dialogs/import_result.py
# Dialog for showing import results.

from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import tk, ttk, ScrolledText


class ImportResultDialog:
    """Dialog for showing import results"""

    def __init__(self, parent, title, result_text):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)

        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        result_text_widget = ScrolledText(main_frame, width=60, height=20)
        result_text_widget.pack(fill=tk.BOTH, expand=True)
        result_text_widget.insert(tk.END, result_text)
        result_text_widget.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
