"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

from education_system.systems.university.shell.gui.main.imports.gui_imports import _lazy_import

# The five modular manager GUIs, as (attribute name, lazily-imported class name).
_GUI_MANAGERS = (
    ("finance_gui", "FinanceManagementGUI"),
    ("student_union_gui", "StudentUnionManagementGUI"),
    ("health_portal_gui", "HealthPortalManagementGUI"),
    ("grade_tracking_gui", "GradeTrackingManagementGUI"),
    ("email_manager_gui", "EmailManagerManagementGUI"),
)


def init_gui_managers(self):
    """Prepare the modular GUI managers.

    These used to be imported *and* instantiated here, during
    ``UnifiedManagementGUI.__init__``. That cost ~10s and pulled in 2,300+
    modules before the main window could be shown, for five feature windows
    the user may never open in a session.

    Each manager is now built on first attribute access instead (see
    ``install_lazy_gui_managers``), so this just resets the cache. Failures are
    still swallowed per-manager, so one broken manager cannot cascade — the
    difference is that the failure now surfaces when that manager is first
    used rather than at startup.
    """
    self._gui_manager_cache = {}


def _build_gui_manager(self, attr, cls_name):
    """Import and instantiate one manager, caching None on failure."""
    try:
        cls = _lazy_import(cls_name)
        return cls(self.root, self.auth) if cls else None
    except Exception as e:
        print(f"Warning: Error initializing {cls_name}: {e}")
        return None


def _make_gui_manager_property(attr, cls_name):
    def getter(self):
        cache = getattr(self, "_gui_manager_cache", None)
        if cache is None:
            cache = self._gui_manager_cache = {}
        if attr not in cache:
            cache[attr] = _build_gui_manager(self, attr, cls_name)
        return cache[attr]

    def setter(self, value):
        # Kept so callers can inject or clear a manager (tests do this).
        cache = getattr(self, "_gui_manager_cache", None)
        if cache is None:
            cache = self._gui_manager_cache = {}
        cache[attr] = value

    getter.__name__ = attr
    return property(getter, setter, doc=f"{cls_name}, built on first access.")


def install_lazy_gui_managers(cls):
    """Install the five manager attributes as build-on-first-access properties.

    These are data descriptors, so they take precedence over anything in the
    instance ``__dict__`` — which is why ``UnifiedManagementGUI.__init__`` must
    not pre-assign these five names.
    """
    for attr, cls_name in _GUI_MANAGERS:
        setattr(cls, attr, _make_gui_manager_property(attr, cls_name))
    return cls
