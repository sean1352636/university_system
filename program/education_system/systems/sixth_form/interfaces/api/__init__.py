"""Sixth-form `api` package.

Exposes a self-contained REST API over the sixth-form domain data and
the parent portal. Import the app factory directly::

    from education_system.systems.sixth_form.interfaces.api import create_app
    app = create_app()

or run it as a module::

    python -m education_system.systems.sixth_form.interfaces.api.server
"""

from education_system.systems.sixth_form.interfaces.api.server import create_app  # noqa: F401

__all__ = ["create_app"]
