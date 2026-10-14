"""FE College learner journey: a learner's record across every system."""

from education_system.platform.cross_system import journey_cli

SYSTEM_KEY = "fe_college"


def show(_ctl) -> None:
    journey_cli.prompt_and_show(SYSTEM_KEY)
