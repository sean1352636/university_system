
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.interfaces.gui.pastoral.internship_management._imports import tk, messagebox, display_internship_menu


class IntegrationsMixin:
    def launch_cli_mode(self):
        """Launch the CLI version for backward compatibility"""
        # Hide the GUI window
        self.root.withdraw()

        try:
            # Import and run the original CLI function
            display_internship_menu()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.internship_management.integrations.dialogs.cli_mode_error', default="CLI Mode Error"), f"Error launching CLI mode: {e}")
        finally:
            # Show the GUI window again
            self.root.deiconify()

    def show_integration_menu(self):
        """Show integration services menu"""
        self.clear_content()

        # Title
        title_frame = tk.Frame(self.content_frame, bg='white')
        title_frame.pack(fill='x', padx=20, pady=(20, 10))

        tk.Label(title_frame, text=_t('gui.pastoral.internship_management.integrations.labels.integration_services', default="Integration Services"),
                font=('Arial', 18, 'bold'), bg='white', fg='#2c3e50').pack(side='left')

        # Create main content frame
        main_frame = tk.Frame(self.content_frame, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Grade Management Integration
        grade_frame = tk.LabelFrame(main_frame, text=_t('gui.pastoral.internship_management.integrations.labels.grade_management', default="Grade Management"),
                                   font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                   padx=10, pady=10)
        grade_frame.pack(fill='x', pady=(0, 15))

        tk.Label(grade_frame, text=_t('gui.pastoral.internship_management.integrations.labels.check_student_grades_and_eligibility_for_internships', default="Check student grades and eligibility for internships"),
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        grade_btn_frame = tk.Frame(grade_frame, bg='white')
        grade_btn_frame.pack(anchor='w')

        if self.auth.check_permission('view_grades') or self.auth.check_permission('view_student_grades'):
            tk.Button(grade_btn_frame, text=_t('gui.pastoral.internship_management.integrations.buttons.view_student_grades', default="View Student Grades"),
                     command=self.open_grade_gui,
                     bg='#3498db', fg='white', font=('Arial', 10),
                     padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        if self.auth.current_user.get('role') == 'student':
            tk.Button(grade_btn_frame, text=_t('gui.pastoral.internship_management.integrations.buttons.check_my_eligibility', default="Check My Eligibility"),
                     command=self.show_my_eligibility,
                     bg='#9b59b6', fg='white', font=('Arial', 10),
                     padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        # Email Integration
        email_frame = tk.LabelFrame(main_frame, text=_t('gui.pastoral.internship_management.integrations.labels.email_management', default="Email Management"),
                                   font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                   padx=10, pady=10)
        email_frame.pack(fill='x', pady=(0, 15))

        tk.Label(email_frame, text=_t('gui.pastoral.internship_management.integrations.labels.send_notifications_and_manage_email_communications', default="Send notifications and manage email communications"),
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        email_btn_frame = tk.Frame(email_frame, bg='white')
        email_btn_frame.pack(anchor='w')

        tk.Button(email_btn_frame, text=_t('gui.pastoral.internship_management.integrations.buttons.open_email_manager', default="Open Email Manager"),
                 command=self.open_email_manager,
                 bg='#e74c3c', fg='white', font=('Arial', 10),
                 padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

        # Finance Integration
        finance_frame = tk.LabelFrame(main_frame, text=_t('gui.pastoral.internship_management.integrations.labels.finance_integration', default="Finance Integration"),
                                     font=('Arial', 14, 'bold'), bg='white', fg='#2c3e50',
                                     padx=10, pady=10)
        finance_frame.pack(fill='x', pady=(0, 15))

        tk.Label(finance_frame, text=_t('gui.pastoral.internship_management.integrations.labels.access_financial_services_and_payment_systems', default="Access financial services and payment systems"),
                font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w', pady=(0, 10))

        finance_btn_frame = tk.Frame(finance_frame, bg='white')
        finance_btn_frame.pack(anchor='w')

        tk.Button(finance_btn_frame, text=_t('gui.pastoral.internship_management.integrations.buttons.open_finance_system', default="Open Finance System"),
                 command=self.open_finance_gui,
                 bg='#27ae60', fg='white', font=('Arial', 10),
                 padx=15, pady=8, relief='flat').pack(side='left', padx=(0, 10))

    def open_email_manager(self):
        """Open email manager GUI"""
        try:
            from education_system.systems.university.interfaces.gui.shell.email.email_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title(_t('gui.pastoral.internship_management.integrations.windows.email_manager', default="Email Manager"))
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror(_t('gui.pastoral.internship_management.integrations.dialogs.error', default="Error"), _t('gui.pastoral.internship_management.integrations.dialogs.email_manager_gui_not_available', default="Email Manager GUI not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.internship_management.integrations.dialogs.error', default="Error"), f"Error opening Email Manager: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
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

    def open_finance_gui(self):
        """Open finance management GUI"""
        try:
            from education_system.systems.university.domains.finance.interfaces.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.root)
            finance_window.title(_t('gui.pastoral.internship_management.integrations.windows.finance_management', default="Finance Management"))
            finance_window.geometry("1000x700")
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
        except ImportError:
            messagebox.showerror(_t('gui.pastoral.internship_management.integrations.dialogs.error', default="Error"), _t('gui.pastoral.internship_management.integrations.dialogs.finance_gui_not_available', default="Finance GUI not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.internship_management.integrations.dialogs.error', default="Error"), f"Error opening Finance GUI: {e}")
