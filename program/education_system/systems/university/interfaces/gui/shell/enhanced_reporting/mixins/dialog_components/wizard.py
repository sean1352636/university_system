"""Wizard dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403


class WizardDialogsMixin:
    def show_template_wizard(self):
        """Show step-by-step template creation wizard"""
        try:
            wizard_window = tk.Toplevel(self.root)
            wizard_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.windows.template_creation_wizard', default="Template Creation Wizard"))
            wizard_window.geometry("800x600")
            wizard_window.transient(self.root)

            # Wizard state
            self.wizard_step = 0
            self.wizard_data = {}

            # Main container
            self.wizard_container = ttk.Frame(wizard_window)
            self.wizard_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Navigation frame
            nav_frame = ttk.Frame(wizard_window)
            nav_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            self.prev_button = ttk.Button(nav_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.buttons.previous', default="< Previous"), command=self.wizard_prev_step)
            self.prev_button.pack(side=tk.LEFT)

            self.next_button = ttk.Button(nav_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.buttons.next', default="Next >"), command=self.wizard_next_step)
            self.next_button.pack(side=tk.RIGHT, padx=(10, 0))

            self.finish_button = ttk.Button(nav_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.buttons.finish', default="Finish"), command=self.wizard_finish,
                                           style='Success.TButton')
            self.finish_button.pack(side=tk.RIGHT)

            ttk.Button(nav_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.buttons.cancel', default="Cancel"), command=wizard_window.destroy).pack(side=tk.RIGHT, padx=(0, 10))

            # Progress indicator
            self.progress_label = ttk.Label(nav_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.labels.step_1_of_4', default="Step 1 of 4"))
            self.progress_label.pack()

            # Start wizard
            self.wizard_window = wizard_window
            self.show_wizard_step()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.dialogs.wizard_error', default="Wizard Error"), f"Failed to open template wizard: {str(e)}")

    def show_wizard_step(self):
        """Show current wizard step"""
        # Clear container
        for widget in self.wizard_container.winfo_children():
            widget.destroy()

        if self.wizard_step == 0:
            self.show_wizard_step_1()
        elif self.wizard_step == 1:
            self.show_wizard_step_2()
        elif self.wizard_step == 2:
            self.show_wizard_step_3()
        elif self.wizard_step == 3:
            self.show_wizard_step_4()

        # Update navigation
        self.prev_button.config(state=tk.NORMAL if self.wizard_step > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.wizard_step < 3 else tk.DISABLED)
        self.finish_button.config(state=tk.NORMAL if self.wizard_step == 3 else tk.DISABLED)
        self.progress_label.config(text=f"Step {self.wizard_step + 1} of 4")

    def show_wizard_step_1(self):
        """Wizard Step 1: Basic Information"""
        ttk.Label(self.wizard_container, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.labels.step_1_basic_information', default="Step 1: Basic Information"),
                 style='Title.TLabel').pack(pady=(0, 20))

        info_frame = ttk.LabelFrame(self.wizard_container, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.labels.template_details', default="Template Details"), padding="20")
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.labels.template_name', default="Template Name:*")).grid(row=0, column=0, sticky=tk.W, pady=10)
        self.wizard_name = tk.StringVar(value=self.wizard_data.get('name', ''))
        ttk.Entry(info_frame, textvariable=self.wizard_name, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

        ttk.Label(info_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.labels.description', default="Description:")).grid(row=1, column=0, sticky=tk.W, pady=10)
        self.wizard_desc = tk.StringVar(value=self.wizard_data.get('description', ''))
        ttk.Entry(info_frame, textvariable=self.wizard_desc, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

    def wizard_next_step(self):
        """Move to next wizard step"""
        # Save current step data
        if self.wizard_step == 0:
            self.wizard_data['name'] = self.wizard_name.get()
            self.wizard_data['description'] = self.wizard_desc.get()

            if not self.wizard_data['name'].strip():
                messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.dialogs.validation_error', default="Validation Error"), _t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.dialogs.template_name_is_required', default="Template name is required"))
                return

        if self.wizard_step < 3:
            self.wizard_step += 1
            self.show_wizard_step()

    def wizard_prev_step(self):
        """Move to previous wizard step"""
        if self.wizard_step > 0:
            self.wizard_step -= 1
            self.show_wizard_step()

    def wizard_finish(self):
        """Complete the wizard and create template"""
        try:
            # Create template from wizard data
            messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.dialogs.success', default="Success"), f"Template '{self.wizard_data.get('name')}' created successfully!")
            self.wizard_window.destroy()
            self.refresh_data()
        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.wizard.dialogs.error', default="Error"), f"Failed to create template: {str(e)}")
