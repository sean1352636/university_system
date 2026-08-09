from .context import *  # noqa: F401,F403
from .panels.tile_pos import TilePOSPanelMixin
from .panels.split_tender import SplitTenderPanelMixin
from .panels.campus_card import CampusCardPanelMixin
from .panels.loyalty_stamps import LoyaltyStampsPanelMixin
from .panels.happy_hours import HappyHoursPanelMixin
from .panels.combos import CombosPanelMixin
from .panels.catering_trays import CateringTraysPanelMixin
from .panels.void_refund import VoidRefundPanelMixin
from .panels.tip_pool import TipPoolPanelMixin
from .panels.offline_mode import OfflineModePanelMixin
from .panels.pickup_slots import PickupSlotsPanelMixin
from .panels.cake_builder import CakeBuilderPanelMixin
from .panels.notifications import NotificationsPanelMixin
from .panels.event_quotes import EventQuotesPanelMixin
from .panels.subscriptions import SubscriptionsPanelMixin
from .dialogs.split_tender import SplitTenderDialogMixin
from .dialogs.cake_builder import CakeBuilderDialogMixin
from .dialogs.event_quote import EventQuoteDialogMixin
from .dialogs.subscription import SubscriptionDialogMixin


class POSTabMixin(TilePOSPanelMixin, SplitTenderPanelMixin, CampusCardPanelMixin, LoyaltyStampsPanelMixin, HappyHoursPanelMixin, CombosPanelMixin, CateringTraysPanelMixin, VoidRefundPanelMixin, TipPoolPanelMixin, OfflineModePanelMixin, PickupSlotsPanelMixin, CakeBuilderPanelMixin, NotificationsPanelMixin, EventQuotesPanelMixin, SubscriptionsPanelMixin, SplitTenderDialogMixin, CakeBuilderDialogMixin, EventQuoteDialogMixin, SubscriptionDialogMixin):
    CAKE_SIZES = ["6\" round (serves 8)", "8\" round (serves 12)", "10\" round (serves 20)", "1/4 sheet (serves 25)", "1/2 sheet (serves 50)"]
    CAKE_FLAVOURS = ["Chocolate", "Vanilla", "Lemon", "Red Velvet", "Carrot", "Funfetti", "Coffee"]
    CAKE_FILLINGS = ["None", "Buttercream", "Ganache", "Cream cheese", "Jam", "Lemon curd"]
    FREQ_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}

    def build_pos_tab(self):
        panels = [
            ("🟦 Tile POS",          self._build_tilepos_panel),
            ("💵 Split-tender",      self._build_split_panel),
            ("🪪 Campus Card",       self._build_campus_panel),
            ("⭐ Loyalty Stamps",    self._build_stamps_panel),
            ("⏰ Happy Hours",       self._build_happy_panel),
            ("🎁 Combos",            self._build_combos_panel),
            ("🧺 Catering Trays",    self._build_catering_panel),
            ("🔐 Void / Quick Refund", self._build_void_panel),
            ("💰 Tip Pool",          self._build_tippool_panel),
            ("📡 Offline Mode",      self._build_offline_panel),
            ("🕒 Pickup Slots",      self._build_slots_panel),
            ("🎂 Cake Builder",      self._build_cakebuilder_panel),
            ("✉️ Notifications",     self._build_notif_panel),
            ("💍 Event Quotes",      self._build_quote_panel),
            ("📦 Subscriptions",     self._build_subs_panel),
        ]
        sub, self._pos_panels = self._lazy_subnotebook(
            self.pos_tab, panels, "POS")
        self.pos_sub = sub
