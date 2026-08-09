"""Compatibility shim — the shell lives in ``interfaces/cli/shell.py``.

The launcher imports ``<system>.cli_main.run`` for every system, so this
keeps that contract while the implementation sits with the rest of the
CLI.
"""
from education_system.systems.apprenticeships.interfaces.cli.shell import *  # noqa: F401,F403
from education_system.systems.apprenticeships.interfaces.cli.shell import (  # noqa: F401
    run,
    run_authenticated,
)
