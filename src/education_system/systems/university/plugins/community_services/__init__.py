"""Community services — an optional university plugin.

Faith and community services run on campus but outside the education core.
Today that is church management: members, donations, prayer requests,
sermons, announcements, volunteers, attendance, small groups and expenses
(``interfaces/gui/church_management``), plus its terminal app
(``interfaces/cli/church_cli.py``).

``plugin.json`` declares capabilities and data handling for
``systems/university/plugins/registry.py``. The ``campus.community-events``
capability it lists has no implementation yet.
"""
