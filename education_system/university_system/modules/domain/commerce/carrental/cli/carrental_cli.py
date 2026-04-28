"""
Car Rental System CLI Interface

Provides command-line interface for car rental management including:
- Vehicle fleet management (add, list, update, status)
- Rental operations (create, start, complete, cancel)
- Payment processing (payments, refunds)
- Maintenance records
- Reports and analytics
"""

from datetime import datetime

from education_system.university_system.modules.domain.commerce.carrental.services.carrental_core import (
    VehicleManager,
    RentalManager,
    TransactionManager,
    ReportManager,
    init_carrental_db,
    VEHICLE_CATEGORIES,
    RENTAL_STATUSES,
    VEHICLE_STATUSES,
)


class CarRentalCLI:
    """Command-line interface for the Car Rental System."""

    def __init__(self):
        """Initialize the Car Rental CLI and database."""
        init_carrental_db()

    def run(self):
        """Run the car rental CLI main loop."""
        while True:
            self._display_main_menu()
            choice = input("\nSelect an option: ").strip()

            if choice == '0':
                print("\nReturning to main menu...")
                break
            elif choice == '1':
                self._vehicles_menu()
            elif choice == '2':
                self._rentals_menu()
            elif choice == '3':
                self._payments_menu()
            elif choice == '4':
                self._reports_menu()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

    # ========== Main Menu ==========

    def _display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("  CAR RENTAL MANAGEMENT SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. Vehicles")
        print("  2. Rentals")
        print("  3. Payments & Transactions")
        print("  4. Reports")
        print("  0. Back to Main Menu")

    # ========== Vehicles ==========

    def _vehicles_menu(self):
        """Vehicles sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  VEHICLE MANAGEMENT")
            print("-" * 50)
            print("  1. Add Vehicle")
            print("  2. List All Vehicles")
            print("  3. Available Vehicles")
            print("  4. View Vehicle Details")
            print("  5. Update Vehicle")
            print("  6. Update Vehicle Status")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._add_vehicle()
                elif choice == '2':
                    self._list_vehicles()
                elif choice == '3':
                    self._available_vehicles()
                elif choice == '4':
                    self._view_vehicle()
                elif choice == '5':
                    self._update_vehicle()
                elif choice == '6':
                    self._update_vehicle_status()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _add_vehicle(self):
        """Add a new vehicle."""
        print("\n--- Add New Vehicle ---")
        reg = input("Registration number: ").strip()
        make = input("Make (e.g. Toyota): ").strip()
        model = input("Model (e.g. Corolla): ").strip()
        year = int(input("Year: ").strip())
        print(f"Categories: {', '.join(VEHICLE_CATEGORIES)}")
        category = input("Category: ").strip()
        daily_rate = float(input("Daily rate: ").strip())
        color = input("Color (optional): ").strip() or None
        seats_input = input("Seats [5]: ").strip()
        seats = int(seats_input) if seats_input else 5
        transmission = input("Transmission (automatic/manual) [automatic]: ").strip() or 'automatic'
        fuel_type = input("Fuel type (petrol/diesel/electric/hybrid) [petrol]: ").strip() or 'petrol'
        mileage_input = input("Current mileage [0]: ").strip()
        mileage = int(mileage_input) if mileage_input else 0
        features = input("Features (optional): ").strip() or None

        vehicle_id = VehicleManager.add_vehicle(
            registration_number=reg, make=make, model=model, year=year,
            category=category, daily_rate=daily_rate,
            color=color, seats=seats, transmission=transmission,
            fuel_type=fuel_type, mileage=mileage, features=features,
        )
        if vehicle_id:
            print(f"\nVehicle added (ID: {vehicle_id})")
        else:
            print("\nFailed to add vehicle.")

    def _list_vehicles(self):
        """List all vehicles."""
        vehicles = VehicleManager.get_all_vehicles()
        if not vehicles:
            print("\nNo vehicles found.")
            return
        print(f"\n{'ID':<5}{'Reg':<12}{'Make':<12}{'Model':<12}{'Year':<6}{'Category':<10}{'Rate':<8}{'Status'}")
        print("-" * 75)
        for v in vehicles:
            print(f"{v['vehicle_id']:<5}{v['registration_number']:<12}"
                  f"{v['make']:<12}{v['model']:<12}{v['year']:<6}"
                  f"{v['category']:<10}{v['daily_rate']:<8.2f}{v['status']}")

    def _available_vehicles(self):
        """List available vehicles."""
        cat = input("Filter by category (blank for all): ").strip() or None
        vehicles = VehicleManager.get_available_vehicles(category=cat)
        if not vehicles:
            print("\nNo available vehicles found.")
            return
        print(f"\n{'ID':<5}{'Reg':<12}{'Make':<12}{'Model':<12}{'Category':<10}{'Rate':<8}{'Seats':<6}{'Trans'}")
        print("-" * 80)
        for v in vehicles:
            print(f"{v['vehicle_id']:<5}{v['registration_number']:<12}"
                  f"{v['make']:<12}{v['model']:<12}{v['category']:<10}"
                  f"{v['daily_rate']:<8.2f}{v['seats']:<6}{v['transmission']}")

    def _view_vehicle(self):
        """View vehicle details."""
        vehicle_id = int(input("Vehicle ID: ").strip())
        v = VehicleManager.get_vehicle(vehicle_id)
        if not v:
            print("Vehicle not found.")
            return
        print(f"\nVehicle ID: {v['vehicle_id']}")
        print(f"Registration: {v['registration_number']}")
        print(f"Make/Model: {v['make']} {v['model']} ({v['year']})")
        print(f"Category: {v['category']}")
        print(f"Color: {v.get('color', 'N/A')}")
        print(f"Seats: {v['seats']}")
        print(f"Transmission: {v['transmission']}")
        print(f"Fuel Type: {v['fuel_type']}")
        print(f"Mileage: {v['mileage']}")
        print(f"Daily Rate: {v['daily_rate']:.2f}")
        print(f"Status: {v['status']}")
        if v.get('features'):
            print(f"Features: {v['features']}")
        if v.get('last_service_date'):
            print(f"Last Service: {v['last_service_date']}")

    def _update_vehicle(self):
        """Update vehicle details."""
        vehicle_id = int(input("Vehicle ID: ").strip())
        print("Leave blank to keep current value:")
        kwargs = {}
        rate = input("Daily rate: ").strip()
        if rate:
            kwargs['daily_rate'] = float(rate)
        color = input("Color: ").strip()
        if color:
            kwargs['color'] = color
        mil = input("Mileage: ").strip()
        if mil:
            kwargs['mileage'] = int(mil)
        features = input("Features: ").strip()
        if features:
            kwargs['features'] = features

        if not kwargs:
            print("No changes specified.")
            return

        updated = VehicleManager.update_vehicle(vehicle_id, **kwargs)
        print("Vehicle updated." if updated else "Failed to update vehicle.")

    def _update_vehicle_status(self):
        """Update vehicle status."""
        vehicle_id = int(input("Vehicle ID: ").strip())
        print(f"Statuses: {', '.join(VEHICLE_STATUSES)}")
        status = input("New status: ").strip()
        updated = VehicleManager.update_vehicle_status(vehicle_id, status)
        print("Status updated." if updated else "Failed to update status.")

    # ========== Rentals ==========

    def _rentals_menu(self):
        """Rentals sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  RENTAL MANAGEMENT")
            print("-" * 50)
            print("  1. Create Rental")
            print("  2. View Rental")
            print("  3. List Rentals by Status")
            print("  4. Start Rental (Pickup)")
            print("  5. Complete Rental (Return)")
            print("  6. Cancel Rental")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._create_rental()
                elif choice == '2':
                    self._view_rental()
                elif choice == '3':
                    self._list_rentals()
                elif choice == '4':
                    self._start_rental()
                elif choice == '5':
                    self._complete_rental()
                elif choice == '6':
                    self._cancel_rental()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _create_rental(self):
        """Create a new rental."""
        print("\n--- Create Rental ---")
        vehicle_id = int(input("Vehicle ID: ").strip())
        customer_id = input("Customer ID: ").strip()
        customer_name = input("Customer name: ").strip()
        license_number = input("License number: ").strip()
        customer_email = input("Email (optional): ").strip() or None
        customer_phone = input("Phone (optional): ").strip() or None
        pickup_date = input("Pickup date (YYYY-MM-DD): ").strip()
        pickup_time = input("Pickup time (HH:MM): ").strip()
        return_date = input("Return date (YYYY-MM-DD): ").strip()
        return_time = input("Return time (HH:MM): ").strip()
        pickup_location = input("Pickup location (optional): ").strip() or None
        return_location = input("Return location (optional): ").strip() or None

        # Get vehicle daily rate
        vehicle = VehicleManager.get_vehicle(vehicle_id)
        if not vehicle:
            print("Vehicle not found.")
            return
        daily_rate = vehicle['daily_rate']
        print(f"Daily rate: {daily_rate:.2f}")

        ins = input("Insurance fee [0]: ").strip()
        insurance_fee = float(ins) if ins else 0
        dep = input("Deposit amount [0]: ").strip()
        deposit = float(dep) if dep else 0

        rental_id = RentalManager.create_rental(
            vehicle_id=vehicle_id, customer_id=customer_id,
            customer_name=customer_name, license_number=license_number,
            pickup_date=pickup_date, pickup_time=pickup_time,
            return_date=return_date, return_time=return_time,
            daily_rate=daily_rate, customer_email=customer_email,
            customer_phone=customer_phone, pickup_location=pickup_location,
            return_location=return_location, insurance_fee=insurance_fee,
            deposit_amount=deposit,
        )
        if rental_id:
            print(f"\nRental created (ID: {rental_id})")
        else:
            print("\nFailed to create rental.")

    def _view_rental(self):
        """View rental details."""
        rental_id = int(input("Rental ID: ").strip())
        r = RentalManager.get_rental(rental_id)
        if not r:
            print("Rental not found.")
            return
        print(f"\nRental #{r['rental_number']}")
        print(f"  Vehicle: {r.get('make', '')} {r.get('model', '')} ({r.get('registration_number', '')})")
        print(f"  Customer: {r['customer_name']}")
        print(f"  License: {r['license_number']}")
        print(f"  Pickup: {r['pickup_date']} {r['pickup_time']}")
        print(f"  Return: {r['return_date']} {r['return_time']}")
        if r.get('actual_return_date'):
            print(f"  Actual Return: {r['actual_return_date']} {r.get('actual_return_time', '')}")
        print(f"  Days: {r['total_days']}")
        print(f"  Daily Rate: {r['daily_rate']:.2f}")
        print(f"  Subtotal: {r['subtotal']:.2f}")
        if r.get('insurance_fee'):
            print(f"  Insurance: {r['insurance_fee']:.2f}")
        if r.get('late_fee'):
            print(f"  Late Fee: {r['late_fee']:.2f}")
        if r.get('damage_fee'):
            print(f"  Damage Fee: {r['damage_fee']:.2f}")
        if r.get('fuel_fee'):
            print(f"  Fuel Fee: {r['fuel_fee']:.2f}")
        print(f"  Total: {r['total_amount']:.2f}")
        print(f"  Deposit: {r.get('deposit_amount', 0):.2f}")
        print(f"  Payment: {r['payment_status']}")
        print(f"  Status: {r['status']}")

    def _list_rentals(self):
        """List rentals by status."""
        print(f"Statuses: {', '.join(RENTAL_STATUSES)} (blank for all)")
        status = input("Status: ").strip() or None
        rentals = RentalManager.get_rentals_by_status(status)
        if not rentals:
            print("\nNo rentals found.")
            return
        print(f"\n{'ID':<5}{'Number':<18}{'Vehicle':<20}{'Customer':<20}{'Pickup':<12}{'Total':<10}{'Status'}")
        print("-" * 95)
        for r in rentals:
            vehicle = f"{r.get('make', '')} {r.get('model', '')}"
            print(f"{r['rental_id']:<5}{r['rental_number']:<18}{vehicle:<20}"
                  f"{r['customer_name']:<20}{r['pickup_date']:<12}"
                  f"{r['total_amount']:<10.2f}{r['status']}")

    def _start_rental(self):
        """Start a rental (vehicle pickup)."""
        rental_id = int(input("Rental ID: ").strip())
        pickup_mileage = int(input("Pickup mileage: ").strip())
        fuel_level = input("Fuel level (full/3-4/half/1-4/empty): ").strip()
        condition_notes = input("Condition notes (optional): ").strip() or None

        started = RentalManager.start_rental(
            rental_id=rental_id, pickup_mileage=pickup_mileage,
            fuel_level=fuel_level, condition_notes=condition_notes,
        )
        print("Rental started." if started else "Failed to start rental.")

    def _complete_rental(self):
        """Complete a rental (vehicle return)."""
        rental_id = int(input("Rental ID: ").strip())
        return_mileage = int(input("Return mileage: ").strip())
        fuel_level = input("Fuel level (full/3-4/half/1-4/empty): ").strip()
        late = input("Late fee [0]: ").strip()
        late_fee = float(late) if late else 0
        damage = input("Damage fee [0]: ").strip()
        damage_fee = float(damage) if damage else 0
        fuel = input("Fuel fee [0]: ").strip()
        fuel_fee = float(fuel) if fuel else 0

        completed = RentalManager.complete_rental(
            rental_id=rental_id, return_mileage=return_mileage,
            fuel_level=fuel_level, late_fee=late_fee,
            damage_fee=damage_fee, fuel_fee=fuel_fee,
        )
        print("Rental completed." if completed else "Failed to complete rental.")

    def _cancel_rental(self):
        """Cancel a rental."""
        rental_id = int(input("Rental ID: ").strip())
        reason = input("Reason (optional): ").strip() or None
        cancelled = RentalManager.cancel_rental(rental_id, reason)
        print("Rental cancelled." if cancelled else "Failed to cancel rental.")

    # ========== Payments ==========

    def _payments_menu(self):
        """Payments sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  PAYMENTS & TRANSACTIONS")
            print("-" * 50)
            print("  1. Record Payment")
            print("  2. Record Refund")
            print("  3. View Transactions")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._record_payment()
                elif choice == '2':
                    self._record_refund()
                elif choice == '3':
                    self._view_transactions()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _record_payment(self):
        """Record a payment."""
        print("\n--- Record Payment ---")
        rental_id = int(input("Rental ID: ").strip())
        customer_id = input("Customer ID: ").strip()
        amount = float(input("Amount: ").strip())
        payment_method = input("Payment method (cash/card/bank_transfer): ").strip()

        txn_id = TransactionManager.record_payment(
            rental_id=rental_id, customer_id=customer_id,
            amount=amount, payment_method=payment_method,
        )
        if txn_id:
            print(f"\nPayment recorded (Transaction ID: {txn_id})")
        else:
            print("\nFailed to record payment.")

    def _record_refund(self):
        """Record a refund."""
        rental_id = int(input("Rental ID: ").strip())
        customer_id = input("Customer ID: ").strip()
        amount = float(input("Refund amount: ").strip())
        reason = input("Reason: ").strip()

        txn_id = TransactionManager.record_refund(
            rental_id=rental_id, customer_id=customer_id,
            amount=amount, reason=reason,
        )
        if txn_id:
            print(f"\nRefund recorded (Transaction ID: {txn_id})")
        else:
            print("\nFailed to record refund.")

    def _view_transactions(self):
        """View transactions."""
        rid = input("Rental ID (blank for all): ").strip()
        rental_id = int(rid) if rid else None
        transactions = TransactionManager.get_transactions(rental_id)
        if not transactions:
            print("\nNo transactions found.")
            return
        print(f"\n{'ID':<6}{'Type':<12}{'Amount':<12}{'Method':<12}{'Status':<12}{'Date'}")
        print("-" * 70)
        for t in transactions:
            print(f"{t.get('transaction_id', ''):<6}"
                  f"{t.get('transaction_type', ''):<12}"
                  f"£{t.get('amount', 0):<10.2f}"
                  f"{t.get('payment_method', ''):<12}"
                  f"{t.get('status', ''):<12}"
                  f"{t.get('created_at', '')}")

    # ========== Reports ==========

    def _reports_menu(self):
        """Reports sub-menu."""
        while True:
            print("\n" + "-" * 50)
            print("  REPORTS & ANALYTICS")
            print("-" * 50)
            print("  1. Fleet Summary")
            print("  2. Revenue Report")
            print("  3. Popular Vehicles")
            print("  4. Admin Report")
            print("  0. Back")

            choice = input("\nSelect an option: ").strip()
            try:
                if choice == '0':
                    break
                elif choice == '1':
                    self._fleet_summary()
                elif choice == '2':
                    self._revenue_report()
                elif choice == '3':
                    self._popular_vehicles()
                elif choice == '4':
                    self._admin_report()
                else:
                    print("Invalid option.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")

    def _fleet_summary(self):
        """Show fleet summary."""
        fleet = ReportManager.get_fleet_summary()
        if not fleet:
            print("\nNo fleet data available.")
            return
        print("\n--- Fleet Summary ---")
        print(f"Total Vehicles: {fleet.get('total_vehicles', 0)}")
        print(f"Available: {fleet.get('available', 0)}")
        print(f"Currently Rented: {fleet.get('rented', 0)}")
        print(f"In Maintenance: {fleet.get('maintenance', 0)}")

    def _revenue_report(self):
        """Show revenue report."""
        start = input("Start date (blank for all time): ").strip() or None
        end = input("End date (blank for present): ").strip() or None
        revenue = ReportManager.get_revenue_report(start, end)
        if not revenue:
            print("\nNo revenue data available.")
            return
        print("\n--- Revenue Report ---")
        print(f"Total Rentals: {revenue.get('total_rentals', 0)}")
        print(f"Completed Rentals: {revenue.get('completed_rentals', 0)}")
        print(f"Total Revenue: £{(revenue.get('total_revenue') or 0):.2f}")
        print(f"Average Rental Value: £{(revenue.get('avg_rental_value') or 0):.2f}")

    def _popular_vehicles(self):
        """Show popular vehicles."""
        limit_input = input("Top N vehicles [10]: ").strip()
        limit = int(limit_input) if limit_input else 10
        vehicles = ReportManager.get_popular_vehicles(limit)
        if not vehicles:
            print("\nNo data available.")
            return
        print(f"\n{'#':<4}{'Make':<12}{'Model':<12}{'Category':<10}{'Rentals':<10}{'Revenue'}")
        print("-" * 55)
        for i, v in enumerate(vehicles, 1):
            print(f"{i:<4}{v['make']:<12}{v['model']:<12}{v['category']:<10}"
                  f"{v['rental_count']:<10}£{(v['total_revenue'] or 0):.2f}")

    def _admin_report(self):
        """Generate admin report."""
        report = ReportManager.generate_admin_report()
        print(report)


def main():
    """Entry point for the Car Rental CLI."""
    cli = CarRentalCLI()
    cli.run()


if __name__ == "__main__":
    main()
