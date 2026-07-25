"""
Audio utility functions with clean initialization (no ALSA warnings)
"""
import os
from contextlib import contextmanager

@contextmanager
def suppress_alsa_warnings():
    """
    Context manager to suppress ALSA and JACK warnings during PyAudio initialization.

    Usage:
        with suppress_alsa_warnings():
            import pyaudio
            p = pyaudio.PyAudio()
        # Use p normally here - warnings are gone
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(devnull)


def init_pyaudio_quietly():
    """
    Initialize PyAudio with all warnings suppressed.

    Returns:
        pyaudio.PyAudio: Initialized PyAudio instance

    Example:
        p = init_pyaudio_quietly()
        # Use p normally
        p.terminate()
    """
    with suppress_alsa_warnings():
        import pyaudio
        p = pyaudio.PyAudio()
    return p
