"""
Status bar widget for the Activity Logger GUI.
"""

from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui._imports import tk, ttk, _t


class StatusBar(ttk.Frame):
    """Status bar showing system information"""

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.configure(style='AL.Card.TFrame')
        self._controller = controller

        # Status variables
        self.status_text = tk.StringVar(value="Ready")
        self.logger_status = tk.StringVar(value="Disconnected")
        self.queue_size = tk.StringVar(value="0")
        self.total_logs = tk.StringVar(value="0")

        self.setup_ui()

    def setup_ui(self):
        """Setup status bar UI"""
        # Left side - main status
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(left_frame, textvariable=self.status_text,
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=5)

        # Right side - stats
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.RIGHT)

        # Exit button
        ttk.Button(
            right_frame,
            text="\U0001f3e0 " + _t("activity_logger.return_main"),
            command=self._handle_return
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Label(right_frame, text=_t("activity_logger.status.logger"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.logger_status,
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(right_frame, text=_t("activity_logger.status.queue"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.queue_size,
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(right_frame, text=_t("activity_logger.status.total_logs"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.total_logs,
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))

    def _handle_return(self):
        if self._controller and hasattr(self._controller, 'return_to_main_menu'):
            self._controller.return_to_main_menu()
            return

        if hasattr(self.master, 'return_to_main_menu'):
            try:
                self.master.return_to_main_menu()
                return
            except Exception:
                pass

        self.master.quit()

    def update_status(self, status: str):
        """Update main status text"""
        self.status_text.set(status)

    def update_logger_status(self, connected: bool):
        """Update logger connection status"""
        self.logger_status.set(_t("activity_logger.status.connected") if connected else _t("activity_logger.status.disconnected"))

    def update_queue_size(self, size: int):
        """Update queue size"""
        self.queue_size.set(str(size))

    def update_total_logs(self, total: int):
        """Update total logs count"""
        self.total_logs.set(str(total))
