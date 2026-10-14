"""Hardened static-asset serving for every portal blueprint.

``send_from_directory`` alone is not enough. Werkzeug's ``safe_join`` rejects
``..`` and absolute paths, but it will happily follow a **symlink inside the
static directory** out to anywhere on disk, and it will serve whatever file
type it finds — so a ``.db``, ``.env``, ``.py`` or backup file that ends up in
an asset directory becomes downloadable. It also has no opinion on directory
requests, so a misconfigured deployment can end up exposing an index.

:func:`send_static_asset` closes all three: it re-checks containment against
the *resolved* path (catching symlink escapes), enforces an extension
allow-list, requires a regular file, and sets the caching and isolation
headers an asset response should carry.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from flask import Response, abort, send_from_directory

from education_system.platform.kernel.core.safe_paths import PathSecurityError, resolve_under

__all__ = ["ASSET_EXTENSIONS", "send_static_asset"]

#: Extensions a public asset route may serve. Anything not listed — including
#: ``.py``, ``.db``, ``.env``, ``.bak``, ``.log``, ``.pem`` and extensionless
#: files — is refused with a 404 rather than a 403, so probing cannot use the
#: status code to confirm a file exists.
ASSET_EXTENSIONS = frozenset({
    ".css", ".js", ".mjs", ".map",
    ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".json", ".webmanifest", ".txt", ".pdf",
})


def send_static_asset(
    directory: str | os.PathLike[str],
    filename: str,
    *,
    allowed_extensions: frozenset[str] | None = None,
    max_age: int | None = None,
) -> Response:
    """Serve ``filename`` from ``directory``, or abort 404 if it is not safe.

    Args:
        directory: The approved asset root. Nothing outside it is ever served.
        filename: The client-supplied relative path.
        allowed_extensions: Overrides :data:`ASSET_EXTENSIONS` for routes with
            a narrower set (e.g. an images-only route).
        max_age: ``Cache-Control: public, max-age=`` value in seconds.
            Defaults to 0 in development and one hour otherwise: a long
            cache on a dev box hides every edit to a JS or CSS file until
            the browser expires it, which reads as "my change did nothing".

    Returns:
        A Flask response with ``X-Content-Type-Options`` and a same-origin
        embedding policy applied.
    """
    if max_age is None:
        from education_system.platform.delivery.api.security.headers import (
            is_development,
        )
        max_age = 0 if is_development() else 3600

    extensions = ASSET_EXTENSIONS if allowed_extensions is None else allowed_extensions
    root = Path(directory)

    try:
        # Resolves symlinks, so an asset dir containing a link to /etc or to
        # the repo's var/ tree cannot be used to read outside the root.
        target = resolve_under(root, filename)
    except PathSecurityError:
        abort(404)

    if target.suffix.lower() not in extensions:
        abort(404)
    # is_file() follows symlinks, which is what we want here: the containment
    # check above already proved the *destination* is inside the root.
    if not target.is_file():
        abort(404)

    # Hand the actual transfer to Flask so range requests, conditional GETs and
    # ETags keep working; the path is now known-good and relative to the root.
    response = send_from_directory(
        str(root), str(target.relative_to(root.resolve(strict=False))), max_age=max_age
    )

    guessed, _ = mimetypes.guess_type(target.name)
    if guessed:
        response.headers["Content-Type"] = guessed
    # An asset served with the wrong Content-Type must never be sniffed into
    # something executable by the browser.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    return response
