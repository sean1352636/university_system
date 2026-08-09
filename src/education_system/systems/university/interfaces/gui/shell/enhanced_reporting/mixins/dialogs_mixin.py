"""Compatibility composition for enhanced-reporting dialogs."""

from .dialog_components import (
    AnalyticsDialogsMixin,
    OperationsDialogsMixin,
    SettingsDialogsMixin,
    SystemDialogsMixin,
    TemplateDialogsMixin,
    WizardDialogsMixin,
)


class DialogsMixin(
    SystemDialogsMixin,
    SettingsDialogsMixin,
    TemplateDialogsMixin,
    OperationsDialogsMixin,
    AnalyticsDialogsMixin,
    WizardDialogsMixin,
):
    """Preserves the original enhanced-reporting dialog API."""


__all__ = ["DialogsMixin"]
