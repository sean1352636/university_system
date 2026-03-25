# Cinema GUI module
from education_system.university_system.modules.domain.cinema.gui.cinema_gui.core.main_gui import CinemaApp
from education_system.university_system.modules.domain.cinema.gui.cinema_gui.database import init_database as init_cinema_database

__all__ = ['CinemaApp', 'init_cinema_database']
