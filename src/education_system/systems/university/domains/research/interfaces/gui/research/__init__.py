"""Research GUIs. ``ResearchGrantsGUI`` / ``launch_research_grants_gui`` are
loaded on first use so importing a sibling (PGR, QA) does not build them."""

__all__ = ['ResearchGrantsGUI', 'launch_research_grants_gui']


def __getattr__(name):
    if name in __all__:
        from education_system.systems.university.domains.research.interfaces.gui.research import (
            research_grants_gui,
        )
        return getattr(research_grants_gui, name)
    raise AttributeError(name)
