# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import email manager availability flag
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import EMAIL_MANAGER_GUI_AVAILABLE

def compose_email(self, email_address):
    """Compose email with recipient pre-filled"""
    try:
        # Try to open the email GUI directly with pre-filled recipient
        if EMAIL_MANAGER_GUI_AVAILABLE:
            from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI

            email_window = tk.Toplevel(self.root)
            _install_clean_close(email_window)
            email_window.title(f"Compose Email to {email_address}")
            email_window.geometry("900x700")
            email_window.transient(self.root)

            # Initialize the email GUI
            email_gui = EmailManagerGUI(email_window, self.auth)

            # Wait a moment then call compose_email with the recipient
            email_window.update_idletasks()

            def safe_compose():
                try:
                    if email_window.winfo_exists():
                        email_gui.compose_email(recipient=email_address)
                except Exception:
                    pass  # Window destroyed

            email_window.after(200, safe_compose)

        elif self.email_manager_gui:
            # Use existing email_manager_gui instance if available
            try:
                self.email_manager_gui.compose_email(recipient=email_address)
            except Exception as e:
                print(f"Could not use existing email GUI: {e}")
                messagebox.showinfo(_t("email_helpers.email_address_title"), _t("email_helpers.compose_email_to", email=email_address))
        else:
            # Final fallback - show email address to copy
            messagebox.showinfo(_t("email_helpers.compose_email_title"),
                              _t("email_helpers.send_email_no_gui", email=email_address))
    except Exception as e:
        print(f"Error opening email composer: {e}")
        messagebox.showinfo(_t("email_helpers.email_address_title"), _t("email_helpers.send_email_to", email=email_address))
def send_email_to_student(self, email, first_name, last_name):
    """Open email composition window for student with pre-filled recipient"""
    # Simply use the compose_email method which now handles recipient pre-filling
    self.compose_email(email)
def show_email_manager(self):
    """Open the Communication/Email Manager GUI in a child window."""
    if self.email_manager_gui:
        self.email_manager_gui.show_email_manager()
    else:
        messagebox.showerror(_t("common.error"), _t("email_helpers.email_manager_not_available"))
def _send_welcome_email_to_student(self, student_id, first_name, last_name, email_address, temp_password, course):
    """Send welcome email to newly created student"""
    try:
        from education_system.university_system.infrastructure.email.email_service import send_template_email

        template_vars = {
            'first_name': first_name,
            'last_name': last_name,
            'student_id': student_id,
            'email_address': email_address,
            'course': course,
            'temp_password': temp_password
        }

        send_template_email('user_management/student_welcome', email_address, template_vars)
        print(f"Welcome email sent successfully to {first_name} {last_name} ({email_address})")

    except Exception as e:
        print(f"Failed to send welcome email to {email_address}: {e}")
        # Show a non-blocking notification about email failure
        try:
            messagebox.showwarning(_t("email_helpers.email_notice_title"),
                _t("email_helpers.student_created_email_failed", email=email_address))
        except Exception:
            print(f"Warning: Welcome email failed for {email_address}")
def _send_email_via_gui(self, to_email, subject, message):
    """Try to send email via email GUI"""
    try:
        # Try to import and use email GUI (EmailGUI is alias for EmailManagerGUI)
        from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI as EmailGUI

        # Create email GUI instance
        email_gui = EmailGUI(self.root, self.auth)

        # Send email through email GUI
        email_gui.send_email(
            to_email=to_email,
            subject=subject,
            message=message
        )

        return True

    except ImportError:
        return False
    except Exception as e:
        print(f"Error sending email via GUI: {e}")
        return False
def _show_welcome_email_fallback(self, first_name, last_name, email_address, subject, message):
    """Show fallback dialog with email details for manual sending"""
    try:
        fallback_window = tk.Toplevel(self.root)
        _install_clean_close(fallback_window)
        fallback_window.title(_t("email_helpers.welcome_email_manual_title"))
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)

        ttk.Label(fallback_window, text=_t("email_helpers.welcome_email_manual_label", first_name=first_name, last_name=last_name),
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text=_t("email_helpers.email_details"), padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        from tkinter.scrolledtext import ScrolledText
        details_text = ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"To: {email_address}\nSubject: {subject}\n\nMessage:\n{message}"

        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text=_t("common.close"),
                  command=fallback_window.destroy).pack(pady=10)
    except Exception as e:
        print(f"Failed to show welcome email fallback: {e}")
def _send_student_update_email(self, student_id, old_data, new_data, course_changed=False, password_reset=False):
    """Send email notification to student about account changes"""
    try:
        # Extract email from old data (assuming it's at index 1)
        email_address = old_data[1]
        if not email_address:
            print(f"No email address found for student {student_id}")
            return

        # Compare old and new data to identify changes
        changes = []
        field_mapping = {
            'title': (old_data[2], new_data['title'], 'Title'),
            'first_name': (old_data[3], new_data['first_name'], 'First Name'),
            'middle_name': (old_data[4], new_data['middle_name'], 'Middle Name'),
            'last_name': (old_data[5], new_data['last_name'], 'Last Name'),
            'gender': (old_data[6], new_data['gender'], 'Gender'),
            'dob': (old_data[7], new_data['dob'], 'Date of Birth'),
            'course': (old_data[9], new_data['course'], 'Course')
        }

        for field, (old_val, new_val, display_name) in field_mapping.items():
            if str(old_val).strip() != str(new_val).strip():
                changes.append(f"• {display_name}: '{old_val}' → '{new_val}'")

        # Build change summary
        changes_text = ""
        if changes:
            changes_text = "The following information has been updated:\n" + "\n".join(changes)

        if course_changed:
            changes_text += f"\n\n⚠️ IMPORTANT: Your course has been changed to {new_data['course']}. This may affect your module enrollments."

        if password_reset:
            new_password = f"{new_data['first_name'].lower()}123456"
            changes_text += f"\n\n🔑 PASSWORD RESET: Your password has been reset to: {new_password}\nPlease change this password upon your next login for security."

        if not changes and not course_changed and not password_reset:
            # No significant changes to notify about
            return

        from education_system.university_system.infrastructure.email.email_service import send_template_email

        template_vars = {
            'student_name': f"{new_data['first_name']} {new_data['last_name']}",
            'updated_fields': changes_text
        }

        send_template_email('user_management/account_information_updated', email_address, template_vars)
        print(f"Student update notification sent to {new_data['first_name']} {new_data['last_name']} ({email_address})")

    except Exception as e:
        print(f"Failed to send student update email to {student_id}: {e}")
        # Non-blocking notification about email failure
        try:
            messagebox.showwarning(_t("email_helpers.email_notice_title"),
                _t("email_helpers.student_updated_email_failed"))
        except Exception:
            print(f"Warning: Update notification email failed for {student_id}")
def _show_update_email_fallback(self, first_name, last_name, email_address, subject, message):
    """Show fallback dialog for student update email"""
    try:
        fallback_window = tk.Toplevel(self.root)
        _install_clean_close(fallback_window)
        fallback_window.title(_t("email_helpers.update_email_manual_title"))
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)

        ttk.Label(fallback_window, text=_t("email_helpers.update_email_manual_label", first_name=first_name, last_name=last_name),
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text=_t("email_helpers.email_details"), padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        from tkinter.scrolledtext import ScrolledText
        details_text = ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"To: {email_address}\nSubject: {subject}\n\nMessage:\n{message}"

        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text=_t("common.close"),
                  command=fallback_window.destroy).pack(pady=10)
    except Exception as e:
        print(f"Failed to show update email fallback: {e}")
