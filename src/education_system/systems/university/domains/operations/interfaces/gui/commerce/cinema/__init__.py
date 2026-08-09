# Cinema GUI module
from education_system.systems.university.domains.operations.interfaces.gui.commerce.cinema.cinema_gui.core.main_gui import CinemaApp
from education_system.systems.university.domains.operations.interfaces.gui.commerce.cinema.cinema_gui.database import init_database as init_cinema_database

__all__ = ['CinemaApp', 'init_cinema_database']
