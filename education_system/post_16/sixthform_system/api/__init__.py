"""Sixth-form `api` package.

Exposes a self-contained REST API over the sixth-form domain data and
the parent portal. Import the app factory directly::

    from education_system.post_16.sixthform_system.api import create_app
    app = create_app()

or run it as a module::

    python -m education_system.post_16.sixthform_system.api.server
"""

from education_system.post_16.sixthform_system.api.server import create_app  # noqa: F401

__all__ = ["create_app"]
