"""Temporary compatibility façade for the split menu router."""
from .menus.main import display_menu
from .features.virtual_classroom import display_virtual_classroom_menu
from .features.financial_aid import display_financial_aid_menu
from .features.communication_hub import display_communication_hub_menu
from .features.accessibility import display_accessibility_tools_menu
from .features.transportation import display_transportation_parking_menu
from .features.administrative_tools import display_administrative_tools_menu
from .features.document_management import display_data_document_management_menu
from .routing.lifecycle import switch_to_gui

__all__ = ['display_menu', 'display_virtual_classroom_menu', 'display_financial_aid_menu', 'display_communication_hub_menu', 'display_accessibility_tools_menu', 'display_transportation_parking_menu', 'display_administrative_tools_menu', 'display_data_document_management_menu', 'switch_to_gui']
