"""Web delivery must not use inline ``on*=`` event-handler attributes.

Every page under ``platform/delivery/web/`` is served with a Content-Security
-Policy of ``script-src 'self'`` (portal pages add a per-response nonce). A
nonce authorises ``<script>`` *blocks*; it never authorises inline handler
attributes, which additionally require ``'unsafe-inline'`` or
``'unsafe-hashes'``. So an ``onclick="..."`` attribute is silently dead in the
browser: no server error, no log line, just a button that does nothing.

That is exactly how the theme toggle, "Sign out", the MFA "Back to login"
button and five parent-portal buttons all shipped broken. Bind listeners with
``addEventListener`` (or delegate from a container) instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src/education_system/platform/delivery/web"
)

#: Files whose contents are served to a browser.
SUFFIXES = {".html", ".js", ".py"}

#: ``on`` + event name + ``=`` at an attribute position, i.e. preceded by
#: whitespace inside a tag. Deliberately not anchored to a quote style so
#: ``onclick=foo`` is caught too.
HANDLER = re.compile(r"""\son[a-z]+\s*=\s*["'`]""", re.IGNORECASE)

#: Lines that merely talk about the pattern (the explanatory comments left
#: beside each fix) are not violations.
COMMENT = re.compile(r"^\s*(//|#|\*|<!--|-->)")

#: Block comments, which may wrap a mention of the pattern across lines that
#: carry no marker of their own.
BLOCKS = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"/\*.*?\*/", re.DOTALL),
)


def _blank_block_comments(text: str) -> str:
    """Blank out block-comment bodies, preserving line numbering."""
    for pattern in BLOCKS:
        text = pattern.sub(
            lambda m: "\n" * m.group(0).count("\n"), text
        )
    return text


def _candidate_files() -> list[Path]:
    return sorted(
        p for p in WEB_ROOT.rglob("*")
        if p.is_file() and p.suffix in SUFFIXES
    )


def test_web_root_exists() -> None:
    """Guard the guard: a moved tree must not silently pass this file."""
    assert WEB_ROOT.is_dir(), f"web delivery tree not found at {WEB_ROOT}"
    assert _candidate_files(), "no servable files found — has the tree moved?"


def test_no_inline_event_handler_attributes() -> None:
    offenders: list[str] = []
    for path in _candidate_files():
        text = _blank_block_comments(
            path.read_text(encoding="utf-8", errors="ignore")
        )
        for lineno, line in enumerate(text.splitlines(), start=1):
            if COMMENT.match(line):
                continue
            if HANDLER.search(line):
                rel = path.relative_to(WEB_ROOT)
                offenders.append(f"  {rel}:{lineno}: {line.strip()[:100]}")

    assert not offenders, (
        "Inline event-handler attributes are blocked by the delivery CSP "
        "(script-src 'self'), so these controls do nothing when clicked:\n"
        + "\n".join(offenders)
        + "\n\nUse addEventListener, or delegate from a container when the "
        "markup is re-rendered. For a page with no script of its own, a "
        "<form method=\"get\"> button reloads without JavaScript."
    )


@pytest.mark.parametrize(
    "sample",
    [
        '<button onclick="doThing()">x</button>',
        "<button onclick='doThing()'>x</button>",
        '<a href="#" onmouseover="peek()">x</a>',
        '<form onsubmit="go()">',
    ],
)
def test_detector_catches_known_shapes(sample: str) -> None:
    """The regex must actually match what it claims to."""
    assert HANDLER.search(sample), sample


@pytest.mark.parametrize(
    "sample",
    [
        '<button type="button" data-logout>Sign out</button>',
        "el.addEventListener('click', () => logout());",
        'const s = "action=on";',
        "// used onclick=\"ParentApp.…\" attributes, which the CSP blocks",
    ],
)
def test_detector_does_not_flag_correct_code(sample: str) -> None:
    assert not HANDLER.search(sample) or COMMENT.match(sample), sample
