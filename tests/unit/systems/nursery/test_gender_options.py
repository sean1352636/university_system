"""Five gender options on the nursery child record, the same as every other
system. Validation only: nothing is written."""

from __future__ import annotations

import pytest

from education_system.systems.nursery.domain.learners.children import children as C

FIVE = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")


def _base(**kw):
    values = {"first_name": "Ada", "last_name": "Test", "date_of_birth": "2023-03-04"}
    values.update(kw)
    return values


def test_same_five_options_as_fe_college():
    from education_system.systems.fe_college import config as fe

    assert C.GENDERS == FIVE == fe.GENDERS


@pytest.mark.parametrize("raw, stored", [
    ("female", "Female"), ("male", "Male"), ("NON-BINARY", "Non-binary"),
    ("prefer not to say", "Prefer not to say"), ("other", "Other"),
])
def test_each_option_accepted_in_any_case(raw, stored):
    assert C._validate(_base(gender=raw))["gender"] == stored


def test_unknown_value_refused():
    with pytest.raises(C.ValidationError, match="Gender must be one of"):
        C._validate(_base(gender="Robot"))
