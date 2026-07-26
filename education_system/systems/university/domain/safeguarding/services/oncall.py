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

from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)


def add_oncall_window(username, full_name, starts_at, ends_at):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_dsl_oncall(username, full_name, starts_at, ends_at) "
        "VALUES (?,?,?,?)",
        (username, full_name, starts_at, ends_at),
    )
    conn.commit()
    conn.close()


def get_oncall_dsl():
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, full_name FROM safeguarding_dsl_oncall "
        "WHERE starts_at<=? AND ends_at>=? ORDER BY id DESC LIMIT 1",
        (now, now),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"username": row[0], "full_name": row[1]}


__all__ = ["add_oncall_window", "get_oncall_dsl"]
