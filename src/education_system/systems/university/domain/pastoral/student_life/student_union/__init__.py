try:
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import (
        display_student_union_menu,
        set_auth,
        set_auth_all,
    )
except Exception as exc:  # pragma: no cover - optional deps may be missing
    _import_error = str(exc)

    def _unavailable(*_args, **_kwargs):
        raise ImportError(f"student_union_core unavailable: {_import_error}")

    display_student_union_menu = _unavailable
    set_auth = _unavailable
    set_auth_all = _unavailable

__all__ = ['display_student_union_menu', 'set_auth', 'set_auth_all']
