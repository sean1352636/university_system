"""One module per screen, grouped by the role view that sees it.

Each module exposes ``TITLE`` and ``open_window(host, **kwargs)``, where
``host`` is the :class:`~education_system.systems.fe_college.gui_main.CollegeGUI`
shell. The shell resolves ``windows.<view>.<key>`` by name, so adding a screen
is a new module plus an entry in ``gui_main.NAVIGATION``.
"""
