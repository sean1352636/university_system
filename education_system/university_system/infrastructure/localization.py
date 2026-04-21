"""Backward-compatibility shim for the legacy localization module.

The standalone JSON loader that lived here has been superseded by the
shared i18n engine (education_system.shared.i18n), accessed via the
university wrapper at education_system.university_system.core.i18n —
which registers the university's own data/locales/ directory alongside
the shared one.

New code should import from ``education_system.university_system.core.i18n``
(or directly from ``education_system.shared.i18n``). This module exists
only to keep existing ``get_translation``/``_t`` imports working.
"""

from education_system.university_system.core.i18n import get_text as get_translation

_t = get_translation

__all__ = ["get_translation", "_t"]
