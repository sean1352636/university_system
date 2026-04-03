"""Backward-compatible flat chatbot module.

The chatbot implementation now lives in the ``university_chatbot`` package.
This bridge preserves older imports and file-path expectations.
"""

from education_system.university_system.utils.ai.university_chatbot import *  # noqa: F401,F403
