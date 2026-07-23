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


def _get_current_user():
    user_id = os.environ.get("EDU_AUTH_USER_ID") or ""
    username = os.environ.get("EDU_AUTH_USERNAME") or ""
    role = os.environ.get("EDU_AUTH_ROLE") or ""
    email = os.environ.get("EDU_AUTH_EMAIL") or ""
    full_name = os.environ.get("EDU_AUTH_FULL_NAME") or ""
    perms_raw = os.environ.get("EDU_AUTH_PERMISSIONS") or ""
    if user_id or username:
        return {
            "id": user_id or username,
            "user_id": user_id or username,
            "username": username or user_id,
            "role": role or "student",
            "email": email,
            "full_name": full_name or username or user_id or "Unknown User",
            "permissions": [p for p in perms_raw.split(",") if p],
        }
    try:
        from education_system.post_18.university_system.infrastructure.auth import get_global_auth

        ga = get_global_auth()
        if ga and getattr(ga, "current_user", None):
            u = dict(ga.current_user)
            u.setdefault("full_name", u.get("username", "Unknown User"))
            u.setdefault("role", "student")
            return u
        return None
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_staff_role(role: str) -> bool:
    """Anyone who isn't a student sees the staff review console."""
    return (role or "").lower() not in ("student", "", "guest")


__all__ = ["_get_current_user", "_is_staff_role"]
