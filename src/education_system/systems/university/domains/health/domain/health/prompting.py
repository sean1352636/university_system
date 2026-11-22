"""Answers for the health portal's prompt-driven services.

The CLI services ask their questions with ``input()``. The GUI panels call
the same services directly with the answers as a dict
(``func(auth, values={...})``): :func:`ask` returns the given answer, or
asks on the terminal when the service runs from the CLI (``values`` is
None). Nothing is patched globally. An answer a service rejects and asks
for again raises :class:`InvalidAnswer` instead of looping, and a question
with no answer given gets ``''`` (the service's default).
"""

from __future__ import annotations


class InvalidAnswer(ValueError):
    """A supplied answer was rejected by the service."""


def ask(values, key: str, prompt: str = "") -> str:
    if values is None:
        return input(prompt)
    used = values.setdefault("__asked__", set())
    if key in used:
        raise InvalidAnswer(f"Invalid value for {key.replace('_', ' ')}: "
                            f"{values.get(key, '')!r}")
    used.add(key)
    value = values.get(key)
    return "" if value is None else str(value)
