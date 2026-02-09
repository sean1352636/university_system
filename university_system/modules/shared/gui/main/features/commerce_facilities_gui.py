# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging

# Import GUI classes needed by this module
from university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import UniversityShopGUI as ShopManagementGUI
from university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI
from university_system.modules.domain.commerce.gui.cafe_system_gui import CafeSystemGUI
from university_system.modules.domain.commerce.gui.takeaway_gui import TakeawayGUI
from university_system.modules.domain.commerce.gui.grocery_gui import GroceryManagementGUI
try:
    from university_system.modules.domain.commerce.gui.bar_gui import BarGUI
    BAR_GUI_AVAILABLE = True
except ImportError:
    BarGUI = None
    BAR_GUI_AVAILABLE = False

# Import GUI availability flags and classes
from university_system.modules.shared.gui.main.imports.gui_imports import (
    SHOP_GUI_AVAILABLE,
    CHARITY_SHOP_GUI_AVAILABLE,
    CharityShopApp,
    PARKING_MANAGEMENT_GUI_AVAILABLE,
    ParkingManagementGUI,
    HOUSING_ACCOMMODATION_GUI_AVAILABLE,
    HousingAccommodationGUI,
    launch_campus_events_gui,
    launch_facilities_management_gui,
    GYM_GUI_AVAILABLE,
    GymGUI,
    DENTIST_GUI_AVAILABLE,
    DentistGUI,
    BUTCHER_GUI_AVAILABLE,
    ButcherGUI,
    BARBER_GUI_AVAILABLE,
    BarberGUI,
    NAILBAR_GUI_AVAILABLE,
    NailBarGUI,
    CARRENTAL_GUI_AVAILABLE,
    CarRentalGUI,
    EQUIPMENT_GUI_AVAILABLE,
    EquipmentGUI,
    PHONESHOP_GUI_AVAILABLE,
    PhoneShopGUI,
    MUSICSHOP_GUI_AVAILABLE,
    MusicShopGUI,
    TAXI_BOOKING_GUI_AVAILABLE,
    TaxiBookingApp,
    TRAIN_STATION_GUI_AVAILABLE,
    TrainStationApp,
    CINEMA_GUI_AVAILABLE,
    CinemaApp,
    init_cinema_database,
)

# Alias for translation function (not exported by import * due to underscore prefix)
from university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_university_shop(self):
    """Launch the University Shop GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_shop"))
        return

    try:
        if not SHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.university_shop"), _t("commerce_facilities.errors.shop_not_available"))
            return

        # Create a new window for the University Shop GUI
        shop_window = tk.Toplevel(self.root)
        shop_window.title(_t("commerce_facilities.titles.university_shop_management"))
        shop_window.geometry("1200x800")
        shop_window.minsize(1000, 600)

        # Center the window
        shop_window.update_idletasks()
        x = (shop_window.winfo_screenwidth() - shop_window.winfo_width()) // 2
        y = (shop_window.winfo_screenheight() - shop_window.winfo_height()) // 2
        shop_window.geometry(f"+{x}+{y}")

        try:
            shop_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Initialize the Shop Management GUI
        shop_gui = ShopManagementGUI(shop_window, self.auth)
        print(_t("commerce_facilities.messages.shop_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.shop_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.shop_error").format(error=e))
def show_charity_shop(self):
    """Launch the Charity Shop GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_charity"))
        return

    try:
        if not CHARITY_SHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.charity_shop"), _t("commerce_facilities.errors.charity_not_available"))
            return

        # Create a new window for the Charity Shop GUI
        charity_window = tk.Toplevel(self.root)
        charity_window.title(_t("commerce_facilities.titles.charity_shop_management"))
        charity_window.geometry("1100x650")
        charity_window.minsize(900, 550)

        # Center the window
        charity_window.update_idletasks()
        x = (charity_window.winfo_screenwidth() - charity_window.winfo_width()) // 2
        y = (charity_window.winfo_screenheight() - charity_window.winfo_height()) // 2
        charity_window.geometry(f"+{x}+{y}")

        try:
            charity_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Initialize the Charity Shop GUI
        charity_gui = CharityShopApp(charity_window, self.auth)
        print(_t("commerce_facilities.messages.charity_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.charity_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.charity_error").format(error=e))
def show_restaurant_management(self):
    """Open the Restaurant Management GUI in a child window (Toplevel)."""
    if not self.restaurant_gui:
        try:
            self.restaurant_gui = RestaurantManagementGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.restaurant_init_failed").format(error=e))
            return

    self.restaurant_gui.show_restaurant_management()
def show_cafe_system(self):
    """Open the Cafe System GUI in a child window (Toplevel)."""
    if not hasattr(self, 'cafe_gui') or not self.cafe_gui:
        try:
            self.cafe_gui = CafeSystemGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.cafe_init_failed").format(error=e))
            return

    self.cafe_gui.show_cafe_system()
def show_takeaway_system(self):
    """Open the Takeaway System GUI in a child window (Toplevel)."""
    if not hasattr(self, 'takeaway_gui') or not self.takeaway_gui:
        try:
            self.takeaway_gui = TakeawayGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.takeaway_init_failed").format(error=e))
            return

    self.takeaway_gui.open_takeaway_gui()
def show_grocery_shop(self):
    """Open the Grocery Shop GUI in a child window (Toplevel)."""
    if not hasattr(self, 'grocery_gui') or not self.grocery_gui:
        try:
            # Use GroceryManagementGUI for staff/admin, regular GroceryGUI for others
            from university_system.modules.domain.commerce.gui.grocery_gui import GroceryManagementGUI
            if self.auth and self.auth.current_user and self.auth.current_user.get('role') in ['admin', 'staff']:
                self.grocery_gui = GroceryManagementGUI(self.root, self.auth)
            else:
                from university_system.modules.domain.commerce.gui.grocery_gui import GroceryGUI
                self.grocery_gui = GroceryGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.grocery_init_failed").format(error=e))
            return

    self.grocery_gui.open_grocery_gui()
def show_bar(self):
    """Open the Bar GUI in a child window (Toplevel)."""
    if not hasattr(self, 'bar_gui') or not self.bar_gui:
        try:
            self.bar_gui = BarGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.bar_init_failed").format(error=e))
            return

    self.bar_gui.show_bar()
def show_parking_management(self):
    """Launch the Parking Management GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_parking"))
        return

    # Check permissions
    if not (self.auth.check_permission('manage_parking') or
            self.auth.check_permission('create_permit') or
            self.auth.check_permission('view_any_permit') or
            self.auth.check_permission('view_own_permit')):
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.no_permission_parking"))
        return

    try:
        # Check if parking GUI is available
        if not PARKING_MANAGEMENT_GUI_AVAILABLE or ParkingManagementGUI is None:
            messagebox.showerror(_t("commerce_facilities.titles.parking_management"), _t("commerce_facilities.errors.parking_not_available"))
            return

        # Create a new window for the Parking Management GUI
        parking_window = tk.Toplevel(self.root)
        parking_window.title(_t("commerce_facilities.titles.parking_management_system"))
        parking_window.geometry("1200x800")
        parking_window.minsize(800, 600)

        # Center the window
        parking_window.update_idletasks()
        x = (parking_window.winfo_screenwidth() - parking_window.winfo_width()) // 2
        y = (parking_window.winfo_screenheight() - parking_window.winfo_height()) // 2
        parking_window.geometry(f"+{x}+{y}")

        try:
            parking_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Initialize the Parking Management GUI in the new window with auth system
        parking_gui = ParkingManagementGUI(parking_window, auth_system=self.auth)

        # Update the current user in the parking GUI if it tracks it separately
        if hasattr(parking_gui, 'current_user'):
            parking_gui.current_user = self.auth.current_user

        print(_t("commerce_facilities.messages.parking_opened_success"))

    except ImportError as e:
        # Fallback to CLI menu if GUI is not available
        messagebox.showinfo(_t("commerce_facilities.titles.parking_management"),
                          _t("commerce_facilities.errors.parking_gui_fallback").format(error=e))
        try:
            from university_system.modules.domain.mobility.services.parking_management import display_parking_menu
            display_parking_menu()
        except ImportError:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.parking_system_unavailable"))
    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.parking_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.parking_error").format(error=e))
def show_housing_accommodations(self):
    """Open Housing Accommodation GUI in a child window."""
    try:
        if not self.auth or not getattr(self.auth, "current_user", None):
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_housing"))
            return

        if not HOUSING_ACCOMMODATION_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.housing_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.housing_accommodation_management"))
        top.geometry("1200x800")
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Embed the GUI (do NOT call .run(); main loop is already running)
        housing_gui = HousingAccommodationGUI(auth_instance=self.auth)
        # Replace the default root with our Toplevel window
        housing_gui.root.destroy()
        housing_gui.root = top
        # Re-create the GUI interface with the new root
        housing_gui.create_main_interface()
        print(_t("commerce_facilities.messages.housing_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.housing_open_failed").format(error=e))
def show_medical_accommodations(self):
    """Launch the Medical Accommodation GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_medical"))
        return

    if not (self.auth.check_permission('manage_accommodations') or
            self.auth.check_permission('view_accommodations') or
            self.auth.check_permission('approve_accommodations')):
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.no_permission_medical"))
        return

    try:
        # Import the accommodation GUI
        import sys
        import os

        # Add the accommodation_gui.py path to sys.path if needed
        accommodation_gui_path = os.path.join(os.path.dirname(__file__), '..')
        if accommodation_gui_path not in sys.path:
            sys.path.insert(0, accommodation_gui_path)

        # Import and launch the medical accommodation GUI
        from university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI, main as accommodation_main

        # Create a new window for the accommodation system
        accommodation_window = tk.Toplevel(self.root)
        accommodation_window.title(_t("commerce_facilities.titles.medical_accommodation_system"))
        accommodation_window.geometry("1200x800")
        accommodation_window.minsize(1000, 700)

        try:
            accommodation_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set accommodation_window as transient: {e}")

        # Center the window
        accommodation_window.update_idletasks()
        x = (accommodation_window.winfo_screenwidth() - accommodation_window.winfo_width()) // 2
        y = (accommodation_window.winfo_screenheight() - accommodation_window.winfo_height()) // 2
        accommodation_window.geometry(f"+{x}+{y}")

        # Initialize the accommodation GUI in the new window with auth
        accommodation_gui = AccommodationGUI(accommodation_window, auth=self.auth)

        print(_t("commerce_facilities.messages.medical_opened_success"))

    except ImportError as e:
        # Fallback to CLI if GUI is not available
        messagebox.showinfo(_t("commerce_facilities.titles.medical_accommodations"),
                          _t("commerce_facilities.errors.medical_gui_fallback").format(error=e))
        try:
            from university_system.modules.domain.housing.services.accommodation import display_accommodation_menu
            display_accommodation_menu()
        except ImportError:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.medical_system_unavailable"))
    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.medical_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.medical_error").format(error=e))
def show_campus_events_gui(self):
    """Launch the Campus Events GUI"""
    launch_campus_events_gui(self.root, self.auth)
def show_facilities_management_gui(self):
    """Launch the Facilities Management GUI"""
    launch_facilities_management_gui(self.root, self.auth)

def show_transportation_parking_gui(self):
    """Launch the Transportation & Parking Management GUI"""
    self._show_feature_gui(
        _t("commerce_facilities.titles.transportation_parking"),
        _t("commerce_facilities.descriptions.transportation_parking"),
        _t("commerce_facilities.messages.use_cli_transportation")
    )

def show_gym_gui(self):
    """Open the Gym/Fitness Center GUI in a child window."""
    from ..imports.gui_imports import GYM_GUI_AVAILABLE, GymGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.gym"), _t("commerce_facilities.errors.login_required_gym"))
            return

        if not GYM_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.gym"), _t("commerce_facilities.errors.gym_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.gym"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Gym GUI
        GymGUI(top, self.auth)
        print(_t("commerce_facilities.messages.gym_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.gym"), _t("commerce_facilities.errors.gym_open_failed").format(error=str(e)))

def show_dentist_gui(self):
    """Open the Dentist/Dental Clinic GUI in a child window."""
    from ..imports.gui_imports import DENTIST_GUI_AVAILABLE, DentistGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.dentist"), _t("commerce_facilities.errors.login_required_dentist"))
            return

        if not DENTIST_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.dentist"), _t("commerce_facilities.errors.dentist_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.dentist"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Dentist GUI
        DentistGUI(top, self.auth)
        print(_t("commerce_facilities.messages.dentist_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.dentist"), _t("commerce_facilities.errors.dentist_open_failed").format(error=str(e)))

def show_butcher_gui(self):
    """Open the Butcher Shop GUI in a child window."""
    from ..imports.gui_imports import BUTCHER_GUI_AVAILABLE, ButcherGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.butcher"), _t("commerce_facilities.errors.login_required_butcher"))
            return

        if not BUTCHER_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.butcher"), _t("commerce_facilities.errors.butcher_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.butcher"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Butcher GUI
        ButcherGUI(top, self.auth)
        print(_t("commerce_facilities.messages.butcher_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.butcher"), _t("commerce_facilities.errors.butcher_open_failed").format(error=str(e)))

def show_barber_gui(self):
    """Open the Barber Shop GUI in a child window."""
    from ..imports.gui_imports import BARBER_GUI_AVAILABLE, BarberGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.barber"), _t("commerce_facilities.errors.login_required_barber"))
            return

        if not BARBER_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.barber"), _t("commerce_facilities.errors.barber_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.barber"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Barber GUI
        BarberGUI(top, self.auth)
        print(_t("commerce_facilities.messages.barber_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.barber"), _t("commerce_facilities.errors.barber_open_failed").format(error=str(e)))

def show_nailbar_gui(self):
    """Open the Nail Bar/Salon GUI in a child window."""
    from ..imports.gui_imports import NAILBAR_GUI_AVAILABLE, NailBarGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.nailbar"), _t("commerce_facilities.errors.login_required_nailbar"))
            return

        if not NAILBAR_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.nailbar"), _t("commerce_facilities.errors.nailbar_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.nailbar"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Nail Bar GUI
        NailBarGUI(top, self.auth)
        print(_t("commerce_facilities.messages.nailbar_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.nailbar"), _t("commerce_facilities.errors.nailbar_open_failed").format(error=str(e)))

def show_carrental_gui(self):
    """Open the Car Rental GUI in a child window."""
    from ..imports.gui_imports import CARRENTAL_GUI_AVAILABLE, CarRentalGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.carrental"), _t("commerce_facilities.errors.login_required_carrental"))
            return

        if not CARRENTAL_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.carrental"), _t("commerce_facilities.errors.carrental_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.carrental"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Car Rental GUI
        CarRentalGUI(top, self.auth)
        print(_t("commerce_facilities.messages.carrental_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.carrental"), _t("commerce_facilities.errors.carrental_open_failed").format(error=str(e)))

def show_equipment_gui(self):
    """Open the Equipment Rental GUI in a child window."""
    from ..imports.gui_imports import EQUIPMENT_GUI_AVAILABLE, EquipmentGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.equipment"), _t("commerce_facilities.errors.login_required_equipment"))
            return

        if not EQUIPMENT_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.equipment"), _t("commerce_facilities.errors.equipment_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.equipment"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Equipment GUI
        EquipmentGUI(top, self.auth)
        print(_t("commerce_facilities.messages.equipment_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.equipment"), _t("commerce_facilities.errors.equipment_open_failed").format(error=str(e)))

def show_phoneshop_gui(self):
    """Open the Phone Shop GUI in a child window."""
    from ..imports.gui_imports import PHONESHOP_GUI_AVAILABLE, PhoneShopGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.phoneshop"), _t("commerce_facilities.errors.login_required_phoneshop"))
            return

        if not PHONESHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.phoneshop"), _t("commerce_facilities.errors.phoneshop_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.phoneshop"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Phone Shop GUI
        PhoneShopGUI(top, self.auth)
        print(_t("commerce_facilities.messages.phoneshop_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.phoneshop"), _t("commerce_facilities.errors.phoneshop_open_failed").format(error=str(e)))

def show_musicshop_gui(self):
    """Open the Music Shop GUI in a child window."""
    from ..imports.gui_imports import MUSICSHOP_GUI_AVAILABLE, MusicShopGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.musicshop"), _t("commerce_facilities.errors.login_required_musicshop"))
            return

        if not MUSICSHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.musicshop"), _t("commerce_facilities.errors.musicshop_not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.titles.musicshop"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Music Shop GUI
        MusicShopGUI(top, self.auth)
        print(_t("commerce_facilities.messages.musicshop_opened_success"))

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.titles.musicshop"), _t("commerce_facilities.errors.musicshop_open_failed").format(error=str(e)))

def show_taxi_booking_gui(self):
    """Open the Taxi Booking GUI in a child window."""
    from ..imports.gui_imports import TAXI_BOOKING_GUI_AVAILABLE, TaxiBookingApp
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.taxi.title"), _t("commerce_facilities.taxi.login_required"))
            return

        if not TAXI_BOOKING_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.taxi.title"), _t("commerce_facilities.taxi.not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.taxi.window_title"))
        top.geometry("1200x800")
        top.minsize(1000, 700)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Taxi Booking GUI
        TaxiBookingApp(top)
        print("Taxi Booking GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.taxi.title"), _t("commerce_facilities.taxi.open_failed", error=str(e)))

def show_train_station_gui(self):
    """Open the Train Station GUI in a child window."""
    from ..imports.gui_imports import TRAIN_STATION_GUI_AVAILABLE, TrainStationApp
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.train.title"), _t("commerce_facilities.train.login_required"))
            return

        if not TRAIN_STATION_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.train.title"), _t("commerce_facilities.train.not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.train.window_title"))
        top.geometry("1000x700")
        top.minsize(900, 600)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Train Station GUI
        TrainStationApp(top)
        print("Train Station GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.train.title"), _t("commerce_facilities.train.open_failed", error=str(e)))

def show_cinema_gui(self):
    """Open the Cinema Booking GUI in a child window."""
    from ..imports.gui_imports import CINEMA_GUI_AVAILABLE, CinemaApp, init_cinema_database
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.cinema.title"), _t("commerce_facilities.cinema.login_required"))
            return

        if not CINEMA_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.cinema.title"), _t("commerce_facilities.cinema.not_available"))
            return

        # Initialize cinema database tables
        if init_cinema_database:
            init_cinema_database()

        top = tk.Toplevel(self.root)
        top.title(_t("commerce_facilities.cinema.window_title"))
        top.geometry("1400x950")
        top.minsize(1100, 700)
        try:
            top.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set window as transient: {e}")

        # Initialize the Cinema GUI
        CinemaApp(top)
        print("Cinema Booking GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.cinema.title"), _t("commerce_facilities.cinema.open_failed", error=str(e)))
