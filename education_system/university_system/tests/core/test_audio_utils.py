"""Tests for university_system.utils.audio_utils."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from education_system.university_system.utils import audio_utils


class TestSuppressAlsaWarnings:
    def test_is_context_manager(self):
        cm = audio_utils.suppress_alsa_warnings()
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")

    def test_restores_stderr_fd_after_exit(self):
        original_fd = os.dup(2)
        try:
            with audio_utils.suppress_alsa_warnings():
                pass
            # After exit, fd 2 should still be valid (writable)
            os.write(2, b"")
        finally:
            os.dup2(original_fd, 2)
            os.close(original_fd)

    def test_restores_stderr_even_on_exception(self):
        original_fd = os.dup(2)
        try:
            with pytest.raises(RuntimeError):
                with audio_utils.suppress_alsa_warnings():
                    raise RuntimeError("boom")
            os.write(2, b"")
        finally:
            os.dup2(original_fd, 2)
            os.close(original_fd)


class TestInitPyaudioQuietly:
    def test_returns_pyaudio_instance(self):
        fake_pyaudio_mod = MagicMock()
        fake_instance = MagicMock()
        fake_pyaudio_mod.PyAudio.return_value = fake_instance
        with patch.dict(sys.modules, {"pyaudio": fake_pyaudio_mod}):
            result = audio_utils.init_pyaudio_quietly()
        assert result is fake_instance
        fake_pyaudio_mod.PyAudio.assert_called_once()
