"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog, scrolledtext

import json

import os

import time

import threading

from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n

init_i18n()

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
