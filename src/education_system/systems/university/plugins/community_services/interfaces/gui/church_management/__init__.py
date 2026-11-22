"""Shared church-management dependencies."""

import html

import tkinter as tk

from tkinter import ttk, messagebox, simpledialog, filedialog

from datetime import datetime, timedelta

import json

import random

import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

# Every page, dialog and service here does ``from <package> import *``. Star
# imports skip underscore names unless they are listed, and ``_t`` is used by
# all of them.
__all__ = [
    "html", "tk", "ttk", "messagebox", "simpledialog", "filedialog",
    "datetime", "timedelta", "json", "random", "logging", "logger", "_t",
]
