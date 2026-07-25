"""Styles, header, and button creation for the Academic Misconduct Panel."""

from education_system.platform.governance.academic_misconduct._imports import tk, ttk, _t, datetime


class MisconductStylesMixin:
    """Mixin providing styling and common UI helpers."""

    def setup_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        style.theme_use('clam')

        # Treeview styling
        style.configure(
            "Custom.Treeview",
            background=self.colors['white'],
            foreground=self.colors['text_dark'],
            fieldbackground=self.colors['white'],
            borderwidth=1,
            rowheight=35
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=self.colors['primary'],
            foreground=self.colors['white'],
            borderwidth=0,
            font=('Segoe UI', 10, 'bold')
        )
        style.map(
            "Custom.Treeview",
            background=[('selected', self.colors['secondary'])],
            foreground=[('selected', self.colors['white'])]
        )

        # Notebook styling
        style.configure(
            "Custom.TNotebook",
            background=self.colors['light'],
            borderwidth=0
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background=self.colors['light'],
            foreground=self.colors['text_dark'],
            padding=[20, 10],
            font=('Segoe UI', 10)
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[('selected', self.colors['white'])],
            foreground=[('selected', self.colors['primary'])],
            expand=[('selected', [1, 1, 1, 0])]
        )

    def create_header(self):
        """Create the application header."""
        header = tk.Frame(self.root, bg=self.colors['primary'], height=70)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)

        # Logo/Title section (centered)
        title_container = tk.Frame(header, bg=self.colors['primary'])
        title_container.pack(expand=True)

        # Show system-specific header
        system_key = getattr(self, 'system_key', None)
        _sys_names = {
            'university': 'University',
            'sixth_form': 'College',
            'secondary': 'Secondary School',
            'primary': 'Primary School',
        }
        if system_key:
            header_text = f"Academic Misconduct Panel - {_sys_names.get(system_key, system_key.title())}"
        else:
            header_text = "Academic Misconduct Panel - All Systems"

        title = tk.Label(
            title_container,
            text=header_text,
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        )
        title.pack()

        subtitle_text = "Super Admin View" if not system_key else "Case Management System"
        subtitle = tk.Label(
            title_container,
            text=subtitle_text,
            font=('Segoe UI', 10),
            fg=self.colors['light'],
            bg=self.colors['primary']
        )
        subtitle.pack()

        # Current date/time on right
        current_time = datetime.now().strftime("%B %d, %Y • %I:%M %p")

        time_label = tk.Label(
            header,
            text=current_time,
            font=('Segoe UI', 9),
            fg=self.colors['light'],
            bg=self.colors['primary']
        )
        time_label.pack(side=tk.RIGHT, padx=20)

    def create_button(self, parent, text, command, style='primary'):
        """Create a styled button."""
        color_map = {
            'primary': (self.colors['secondary'], self.colors['white'], self.colors['primary']),
            'success': (self.colors['success'], self.colors['white'], '#1e8449'),
            'warning': (self.colors['warning'], self.colors['white'], '#d68910'),
            'danger': (self.colors['danger'], self.colors['white'], '#c0392b'),
            'info': (self.colors['info'], self.colors['white'], '#138496'),
            'secondary': (self.colors['light'], self.colors['text_dark'], self.colors['border'])
        }

        bg, fg, hover_bg = color_map.get(style, color_map['secondary'])

        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=('Segoe UI', 9, 'bold'),
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground=fg,
            relief='flat',
            padx=12,
            pady=6,
            cursor='hand2',
            bd=0
        )

        btn.bind('<Enter>', lambda e: btn.configure(bg=hover_bg))
        btn.bind('<Leave>', lambda e: btn.configure(bg=bg))

        return btn
