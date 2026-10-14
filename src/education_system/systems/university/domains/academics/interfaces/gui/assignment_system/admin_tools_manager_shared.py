"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, scrolledtext, filedialog
from education_system.systems.university.domains.academics.interfaces.gui.assignment_system._dialogs import messagebox

import json

import csv

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
