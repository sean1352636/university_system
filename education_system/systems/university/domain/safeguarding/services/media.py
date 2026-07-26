import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

_QUICK_EXIT_URL = "https://www.google.com/search?q=weather"


def quick_exit():
    """Safe-exit: blank the screen, navigate browser to an innocuous page, then quit."""
    try:
        webbrowser.open_new_tab(_QUICK_EXIT_URL)
    except Exception:
        pass
    try:
        for w in tk._default_root.winfo_children() if tk._default_root else []:
            try:
                w.destroy()
            except tk.TclError:
                pass
        if tk._default_root is not None:
            tk._default_root.destroy()
    except Exception:
        pass
    os._exit(0)


def maybe_transcribe(audio_path: str) -> str | None:
    """Best-effort transcription. Returns None if no engine is available."""
    if not audio_path:
        return None
    try:
        import speech_recognition as sr  # type: ignore

        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as src:
            audio = r.record(src)
        return r.recognize_google(audio)
    except Exception:
        return None


__all__ = ["_QUICK_EXIT_URL", "quick_exit", "maybe_transcribe"]
