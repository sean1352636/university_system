"""
Cinema Booking System - Entry Point
"""
import tkinter as tk

from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.core.main_gui import CinemaApp
from education_system.systems.university.interfaces.gui.operations.commerce.cinema.cinema_gui.database import init_database


def main():
    init_database()
    root = tk.Tk()
    app = CinemaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
