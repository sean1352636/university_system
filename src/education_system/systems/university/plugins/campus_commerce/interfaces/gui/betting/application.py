"""Composed betting shop GUI application."""

from .base import BettingShopBaseMixin
from .services import PaymentMixin, ReceiptMixin
from .shared import _t, messagebox, traceback
from .tabs import (
    AccountTabMixin,
    AdminTabMixin,
    CasinoTabMixin,
    PredictionsTabMixin,
    SportsTabMixin,
)


class BettingShopGUI(
    BettingShopBaseMixin,
    SportsTabMixin,
    PredictionsTabMixin,
    CasinoTabMixin,
    AccountTabMixin,
    PaymentMixin,
    ReceiptMixin,
    AdminTabMixin,
):
    """University betting shop window composed from focused UI mixins."""


def launch_betting_shop_gui(root, auth):
    """Launch the Betting Shop GUI"""
    try:
        BettingShopGUI(root, auth)
    except Exception as e:
        messagebox.showerror(
            _t("common.error", default="Error"),
            _t("betting.errors.launch_failed", default="Failed to launch Betting Shop: {error}").format(error=str(e))
        )
        print(f"Betting Shop GUI error: {traceback.format_exc()}")


__all__ = ["BettingShopGUI", "launch_betting_shop_gui"]
