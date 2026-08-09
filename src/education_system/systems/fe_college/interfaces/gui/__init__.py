"""Tk desktop interface for the FE College system.

The shell lives in ``fe_college.gui_main``; this package holds what it renders:

* :mod:`widgets`         shared building blocks (tables, forms, KPI tiles)
* :mod:`timetable_grid`  the weekly grid, shared by three windows
* :mod:`controllers`     the controller windows talk to instead of services
* :mod:`windows`         one module per screen, grouped by role view
"""
