"""Translation strings for the superadmin dashboard.

``_TRANSLATIONS`` is rebound by :func:`load_translations`; import the functions,
never the dict itself.
"""

from pathlib import Path

_TRANSLATIONS = {}  # populated by load_translations()


def load_translations(locale="en"):
    """Load translation strings from shared locale JSON if available.

    Falls back to empty dict so _t() returns the English default key.
    """
    global _TRANSLATIONS
    # Locale data lives in the gitignored var/ tree at the repo root (ADR 0018),
    # never inside the package.
    # this file -> superadmin_dashboard -> gui -> delivery -> platform -> education_system
    #   -> src -> <repo root>
    repo_root = Path(__file__).resolve().parents[6]
    locales_dir = repo_root / "var" / "data" / "platform" / "locales" / locale
    json_path = locales_dir / "superadmin_dashboard.json"
    if json_path.exists():
        try:
            import json
            with open(json_path, encoding="utf-8") as f:
                _TRANSLATIONS = json.load(f)
        except Exception:
            _TRANSLATIONS = {}
    else:
        _TRANSLATIONS = {}


def _t(key, default=None):
    """Return translated string for *key*, falling back to *default* or the key itself."""
    return _TRANSLATIONS.get(key, default or key)
