"""Tests for ``education_system.nursery_system.menu`` — the single source of
truth for the nursery navigation shared by the CLI and GUI.
"""

from __future__ import annotations


def test_nav_categories_shape():
    from education_system.nursery_system.menu import NAV_CATEGORIES
    assert isinstance(NAV_CATEGORIES, list)
    assert NAV_CATEGORIES, "expected at least one category"
    labels = [cat for cat, _items in NAV_CATEGORIES]
    # No duplicate top-level category labels.
    assert len(labels) == len(set(labels))
    for _cat, items in NAV_CATEGORIES:
        assert items and all(isinstance(i, str) for i in items)
        # No duplicate items inside a single category.
        assert len(items) == len(set(items))


def test_expected_eyfs_categories_present():
    from education_system.nursery_system.menu import NAV_CATEGORIES
    labels = {cat for cat, _items in NAV_CATEGORIES}
    for expected in (
        "Children & Admissions",
        "EYFS Learning & Development",
        "Safeguarding & Welfare",
        "System",
    ):
        assert expected in labels, expected


def test_cli_and_gui_use_the_same_catalogue():
    from education_system.nursery_system import menu
    from education_system.nursery_system import cli_main
    assert cli_main.NAV_CATEGORIES is menu.NAV_CATEGORIES
