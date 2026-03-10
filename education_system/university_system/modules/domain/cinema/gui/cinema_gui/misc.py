"""
Cinema Booking System - Entry Point
"""
import tkinter as tk

from .core.main_gui import CinemaApp
from .database import init_database


def main():
    init_database()
    root = tk.Tk()
    app = CinemaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
