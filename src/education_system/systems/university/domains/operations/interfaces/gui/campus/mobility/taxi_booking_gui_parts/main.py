"""Extracted function implementation."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def main():
    """Main entry point"""
    root = tk.Tk()

    # Center window on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 1200) // 2
    y = (screen_height - 800) // 2
    root.geometry(f"1200x800+{x}+{y}")

    app = TaxiBookingApp(root)
    root.mainloop()
