# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

# GUI classes — imported lazily when each function is called
from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import _lazy_import

# Import GUI availability flags and classes
from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import (
    SHOP_GUI_AVAILABLE,
    CHARITY_SHOP_GUI_AVAILABLE,
    CharityShopApp,
    PARKING_MANAGEMENT_GUI_AVAILABLE,
    ParkingManagementGUI,
    HOUSING_ACCOMMODATION_GUI_AVAILABLE,
    HousingAccommodationGUI,
    launch_campus_events_gui,
    launch_facilities_management_gui,
)

# Alias for translation function (not exported by import * due to underscore prefix)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_university_shop(self):
    """Launch the University Shop GUI in a child window.

    If a contextual right-click brought the user here (e.g. Library →
    "Buy in University Shop"), the pending academic context dict on
    ``self._last_academic_context`` is consumed and the shop's product
    browser is navigated + its search box pre-populated with the book
    title (or ISBN) so the matching products surface immediately."""
    if not self.auth.current_user:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.login_required_shop"))
        return

    ctx = None
    try:
        from education_system.systems.university.interfaces.gui.shell.main.features.academic_link_bar import (
            consume_context as _consume_academic_context,
        )
        ctx = _consume_academic_context(self)
    except Exception:
        logger.debug("university shop: could not consume academic context", exc_info=True)

    try:
        if not SHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.university_shop"), _t("commerce_facilities.errors.shop_not_available"))
            return

        # Create a new window for the University Shop GUI
        shop_window = tk.Toplevel(self.root)
        _install_clean_close(shop_window)
        shop_window.title(_t("commerce_facilities.titles.university_shop_management"))
        shop_window.geometry("1400x900")
        shop_window.minsize(1200, 800)

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
        from education_system.systems.university.interfaces.gui.operations.commerce.shop_management_gui.main_gui import UniversityShopGUI as ShopManagementGUI
        shop_gui = ShopManagementGUI(shop_window, self.auth)
        print(_t("commerce_facilities.messages.shop_opened_success"))

        if ctx and (ctx.get("book_title") or ctx.get("isbn")
                    or ctx.get("book_id")):
            try:
                shop_window.title(
                    shop_window.title()
                    + f"  ◆ {ctx.get('book_title') or ctx.get('isbn') or ctx.get('book_id')}"
                )
            except Exception:
                pass
            try:
                shop_window.after(
                    50,
                    lambda g=shop_gui, c=ctx: _open_shop_with_book_context(g, c),
                )
            except Exception:
                logger.exception("shop context navigation failed")

    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.shop_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.shop_error").format(error=e))


def _open_shop_with_book_context(shop_gui, ctx):
    """Navigate a freshly-opened UniversityShopGUI to the product
    browser and pre-fill the search box with the book title / ISBN /
    book_id supplied by the academic context. Best-effort — if the
    GUI doesn't expose the expected hooks the helper logs and returns."""
    try:
        browse = getattr(shop_gui, "show_product_browser", None) or \
                 getattr(shop_gui, "browse_products", None)
        if callable(browse):
            browse()
    except Exception:
        logger.debug("shop context: could not open product browser", exc_info=True)

    try:
        search_var = getattr(shop_gui, "search_var", None)
        if search_var is None:
            return
        term = (ctx.get("book_title") or ctx.get("isbn")
                or ctx.get("book_id"))
        if not term:
            return
        search_var.set(str(term))
        do_search = getattr(shop_gui, "search_products", None)
        if callable(do_search):
            do_search()
    except Exception:
        logger.debug("shop context: search prefill failed", exc_info=True)
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
        _install_clean_close(charity_window)
        charity_window.title(_t("commerce_facilities.titles.charity_shop_management"))
        charity_window.geometry("1400x900")
        charity_window.minsize(1200, 800)

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
            RestaurantManagementGUI = _lazy_import("RestaurantManagementGUI")
            self.restaurant_gui = RestaurantManagementGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.restaurant_init_failed").format(error=e))
            return

    self.restaurant_gui.show_restaurant_management()
def show_cafe_system(self):
    """Open the Cafe System GUI in a child window (Toplevel)."""
    if not hasattr(self, 'cafe_gui') or not self.cafe_gui:
        try:
            CafeSystemGUI = _lazy_import("CafeSystemGUI")
            self.cafe_gui = CafeSystemGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.cafe_init_failed").format(error=e))
            return

    self.cafe_gui.show_cafe_system()
def show_takeaway_system(self):
    """Open the Takeaway System GUI in a child window (Toplevel)."""
    if not hasattr(self, 'takeaway_gui') or not self.takeaway_gui:
        try:
            TakeawayGUI = _lazy_import("TakeawayGUI")
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
            from education_system.systems.university.interfaces.gui.operations.commerce.grocery_gui import GroceryManagementGUI
            if self.auth and self.auth.current_user and self.auth.current_user.get('role') in ['admin', 'staff']:
                self.grocery_gui = GroceryManagementGUI(self.root, self.auth)
            else:
                from education_system.systems.university.interfaces.gui.operations.commerce.grocery_gui import GroceryGUI
                self.grocery_gui = GroceryGUI(self.root, self.auth)
        except Exception as e:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.grocery_init_failed").format(error=e))
            return

    self.grocery_gui.open_grocery_gui()
def show_bar(self):
    """Open the Bar GUI in a child window (Toplevel)."""
    if not hasattr(self, 'bar_gui') or not self.bar_gui:
        try:
            BarGUI = _lazy_import("BarGUI")
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
        _install_clean_close(parking_window)
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
            from education_system.systems.university.domain.operations.campus.mobility.services.parking_management import display_parking_menu
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
        _install_clean_close(top)
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
        from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation import AccommodationGUI, main as accommodation_main

        # Create a new window for the accommodation system
        accommodation_window = tk.Toplevel(self.root)
        _install_clean_close(accommodation_window)
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
            from education_system.systems.university.domain.operations.campus.housing.services.accommodation import display_accommodation_menu
            display_accommodation_menu()
        except ImportError:
            messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.medical_system_unavailable"))
    except Exception as e:
        messagebox.showerror(_t("commerce_facilities.errors.error"), _t("commerce_facilities.errors.medical_open_failed").format(error=str(e)))
        print(_t("commerce_facilities.messages.medical_error").format(error=e))
def show_campus_events_gui(self):
    """Launch Campus Events inside the main GUI's content notebook
    when a workspace is available, falling back to a Toplevel
    otherwise — same pattern as Student Records (8.117.38)."""
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        from education_system.systems.university.domain.operations.campus.services.campus_events_gui import CampusEventsGUI
        opener("Campus Events", lambda host: CampusEventsGUI(host, self.auth))
        return
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import GYM_GUI_AVAILABLE, GymGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.gym"), _t("commerce_facilities.errors.login_required_gym"))
            return

        if not GYM_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.gym"), _t("commerce_facilities.errors.gym_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import DENTIST_GUI_AVAILABLE, DentistGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.dentist"), _t("commerce_facilities.errors.login_required_dentist"))
            return

        if not DENTIST_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.dentist"), _t("commerce_facilities.errors.dentist_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import BUTCHER_GUI_AVAILABLE, ButcherGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.butcher"), _t("commerce_facilities.errors.login_required_butcher"))
            return

        if not BUTCHER_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.butcher"), _t("commerce_facilities.errors.butcher_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import BARBER_GUI_AVAILABLE, BarberGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.barber"), _t("commerce_facilities.errors.login_required_barber"))
            return

        if not BARBER_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.barber"), _t("commerce_facilities.errors.barber_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import NAILBAR_GUI_AVAILABLE, NailBarGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.nailbar"), _t("commerce_facilities.errors.login_required_nailbar"))
            return

        if not NAILBAR_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.nailbar"), _t("commerce_facilities.errors.nailbar_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import CARRENTAL_GUI_AVAILABLE, CarRentalGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.carrental"), _t("commerce_facilities.errors.login_required_carrental"))
            return

        if not CARRENTAL_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.carrental"), _t("commerce_facilities.errors.carrental_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import EQUIPMENT_GUI_AVAILABLE, EquipmentGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.equipment"), _t("commerce_facilities.errors.login_required_equipment"))
            return

        if not EQUIPMENT_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.equipment"), _t("commerce_facilities.errors.equipment_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import PHONESHOP_GUI_AVAILABLE, PhoneShopGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.phoneshop"), _t("commerce_facilities.errors.login_required_phoneshop"))
            return

        if not PHONESHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.phoneshop"), _t("commerce_facilities.errors.phoneshop_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import MUSICSHOP_GUI_AVAILABLE, MusicShopGUI
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.titles.musicshop"), _t("commerce_facilities.errors.login_required_musicshop"))
            return

        if not MUSICSHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.titles.musicshop"), _t("commerce_facilities.errors.musicshop_not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import TAXI_BOOKING_GUI_AVAILABLE, TaxiBookingApp
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.taxi.title"), _t("commerce_facilities.taxi.login_required"))
            return

        if not TAXI_BOOKING_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.taxi.title"), _t("commerce_facilities.taxi.not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import TRAIN_STATION_GUI_AVAILABLE, TrainStationApp
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("commerce_facilities.train.title"), _t("commerce_facilities.train.login_required"))
            return

        if not TRAIN_STATION_GUI_AVAILABLE:
            messagebox.showerror(_t("commerce_facilities.train.title"), _t("commerce_facilities.train.not_available"))
            return

        top = tk.Toplevel(self.root)
        _install_clean_close(top)
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
    from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import CINEMA_GUI_AVAILABLE, CinemaApp, init_cinema_database
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
        _install_clean_close(top)
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
