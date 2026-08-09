"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_fallback_interface(self):
    """Create minimal fallback interface"""
    self.root = tk.Tk()
    self.root.title(_t("gui.error_mode_title"))
    self.root.geometry("400x300")
    try:
        from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import (
            install_destroy_race_filter,
        )
        install_destroy_race_filter(self.root)
    except Exception:
        pass

    error_frame = ttk.Frame(self.root, padding="20")
    error_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(error_frame, text=_t("gui.error_initializing"), font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(error_frame, text=_t("gui.system_minimal_mode"), foreground="red", wraplength=350).pack(pady=10)
    ttk.Button(error_frame, text=_t("common.close"), command=self.root.quit).pack(pady=10)
