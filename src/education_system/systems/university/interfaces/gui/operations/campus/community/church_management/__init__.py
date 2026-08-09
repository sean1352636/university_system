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
