"""Import-boundary tests for the Safeguarding vertical slice.

Safeguarding is the first slice the document asked to be *re-layered* rather
than relocated: the flat ``domain/safeguarding`` package mixed business rules
with API, authentication, configuration, cryptography and database code. It now
splits into domain / application / infrastructure / interfaces.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Safeguarding still violates. The allow-list is a
ratchet, so it can only shrink — and at three entries it is already the
smallest of any slice, despite this being the messiest starting point.
"""

from __future__ import annotations

SLICE = "safeguarding"

_UNI = "education_system.systems.university"

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # The "quick exit" panic control lives in a service: it tears down every Tk
    # window and opens a neutral page, so a learner in danger can leave the
    # screen instantly. Genuinely user-facing behaviour, and genuinely safety
    # critical — but an application service cannot be driven from the API or the
    # CLI while it reaches for a screen. It belongs behind a port that the GUI
    # implements.
    ("application/services/media.py", "tkinter"),
    ("application/services/media.py", "webbrowser"),
    # Safeguarding integrations read Pastoral wellness records directly. The
    # document is explicit that referrals must cross this boundary "through an
    # explicit port/event, never a table import". Both are slices now, so this is
    # an explicit cross-slice read of medical data.
    (
        "application/services/integrations.py",
        f"{_UNI}.domains.pastoral.domain.health.wellness",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)


def test_layers_exist(slice_violations) -> None:
    """The re-layering produced all four layers, not just a relocation."""
    from pathlib import Path

    root = (
        Path(__file__).resolve().parents[6]
        / "src/education_system/systems/university/domains/safeguarding"
    )
    for layer in ("domain", "application", "infrastructure", "interfaces"):
        assert (root / layer).is_dir(), f"missing {layer}/ in the safeguarding slice"
