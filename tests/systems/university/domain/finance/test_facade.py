from unittest.mock import patch

from education_system.systems.university.domain.finance import facade


def test_finance_facade_resolves_every_legacy_gui_operation():
    assert len(facade._FUNCTION_MODULES) == 69
    assert facade.UNAVAILABLE_FUNCTIONS == {}
    assert all(
        callable(getattr(facade, name))
        and not getattr(getattr(facade, name), "__finance_unavailable__", False)
        for name in facade._FUNCTION_MODULES
    )


def test_one_missing_operation_does_not_disable_resolved_operations():
    working_operation = facade.assign_to_collection_agency

    with patch.object(facade, "import_module", side_effect=ImportError("optional dependency")):
        unavailable = facade._resolve("optional_operation", "optional.module")

    assert getattr(unavailable, "__finance_unavailable__", False)
    assert facade.assign_to_collection_agency is working_operation
