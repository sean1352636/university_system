"""Draws the pupil profile boxes from the linked areas (safeguarding flag,
SEND / medical / pupil premium, attendance case / wellbeing / complaints,
trips / dinner money, parents' evenings / letters). The content comes from
:mod:`modules.pupils.domain.profile_linked`, shared with the terminal profile."""

from __future__ import annotations

from tkinter import ttk

from education_system.systems.secondary.modules.pupils.domain import profile_linked as PL
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal

_COLOURS = {"": "", "warn": "#a60", "bad": "#a33"}


def draw_safeguarding_flag(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    text = PL.safeguarding_flag(pupil, principal=principal)
    if text:
        ttk.Label(parent, text=f"🛡 {text}", foreground=_COLOURS["bad"],
                  font=("", 10, "bold")).pack(anchor="w", pady=(4, 0))


def draw_linked(parent: ttk.Frame, pupil: P.Pupil, *, principal: Principal) -> None:
    for title, lines in PL.sections(pupil, principal=principal):
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.pack(fill="x", pady=(8, 0))
        for text, level in lines:
            ttk.Label(box, text=text, foreground=_COLOURS.get(level, ""), wraplength=760,
                      justify="left").pack(anchor="w")


__all__ = ["draw_linked", "draw_safeguarding_flag"]
