from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


class _PathProxy:
    def __init__(self, path: Path):
        self._path = Path(path)
        self.exists = MagicMock(return_value=self._path.exists())
        self.parent = MagicMock()
        self.parent.mkdir = MagicMock()

    def __fspath__(self):
        return str(self._path)

    def __str__(self):
        return str(self._path)

    def __repr__(self):
        return repr(self._path)


@pytest.fixture
def mock_paths():
    with pytest.MonkeyPatch.context() as mp:
        import education_system.university_system.modules.shared.utils.config as config_mod

        mock = MagicMock()
        mock.EMAIL_CONFIG_PATH = _PathProxy(Path('/tmp/email_config.json'))
        mock.EMAIL_TEMPLATES_DIR = Path('/tmp/templates')
        mp.setattr(config_mod, 'paths', mock)
        yield mock
