"""The Research Portal's shared screen pieces now live in
``university/infrastructure/ui/record_screens`` so other domains (graduation,
alumni) can use them without reaching into Academics. Re-exported here."""

from education_system.systems.university.infrastructure.ui.record_screens import *  # noqa: F401,F403
from education_system.systems.university.infrastructure.ui.record_screens import (  # noqa: F401
    TITLE,
    Detail,
    Field,
    FormDialog,
    RecordTab,
    ask,
    ask_text,
    call,
    confirm,
    fill,
    info,
    make_tree,
    money,
    nice,
    selected,
    send_emails,
    staff_choices,
)
