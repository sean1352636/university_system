"""Methods _show_plagiarism_email_fallback through run."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import main_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PlagiarismCheckerGUI:
    def _show_plagiarism_email_fallback(self, email, subject, message, result_data):
        """Show fallback dialog for plagiarism report email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_show_plagiarism_email_fallb.windows.plagiarism_report_email_manual_send', default="Plagiarism Report Email - Manual Send"))
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_show_plagiarism_email_fallb.labels.email_system_unavailable_please_manually_send_this_report', default="Email system unavailable. Please manually send this report:"),
                     font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = ttk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text=_t('gui.academics.plagiarism_main_gui.main_gui_parts.plagiarismcheckergui_show_plagiarism_email_fallb.buttons.close', default="Close"), command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show plagiarism email fallback: {e}")

    def auto_send_report_on_completion(self, result_data):
        """Automatically send report when plagiarism check completes"""
        try:
            # Get user email from auth system
            user_email = None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user_email = self.auth.current_user.get('email')

            if user_email:
                self.send_plagiarism_report_via_email(result_data, user_email)
            else:
                print("No user email available for auto-send")
        except Exception as e:
            print(f"Failed to auto-send plagiarism report: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if getattr(self, 'launched_from_main', False):
                # When launched from main system, simply close this window
                root_widget.destroy()
                return

            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from education_system.systems.university.interfaces.gui.shell.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Run the GUI application"""
        self.root.mainloop()
