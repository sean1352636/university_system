"""
IP / Patents Menu - Disclosures, patents, licenses and revenue CLI.

Wired to IPManager (the same manager the IP GUI uses).
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.ip_manager import (
    IPManager,
)


def display_ip_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the intellectual property management menu."""
    while True:
        print("\n" + "=" * 60)
        print("INTELLECTUAL PROPERTY / PATENTS")
        print("=" * 60)

        print("\n  1. My Disclosures")
        print("  2. New Disclosure")
        print("  3. Submit Disclosure")
        print("  4. View Patents")
        print("  5. View Licenses")
        print("  6. Add License")
        print("  7. Record License Revenue")

        if is_admin:
            print("\n--- Administration ---")
            print("  8. Create Patent")
            print("  9. Update Patent Status")
            print("  10. Portfolio Summary")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _my_disclosures(user_id)
        elif choice == '2':
            _new_disclosure(user_id)
        elif choice == '3':
            _submit_disclosure(user_id)
        elif choice == '4':
            _view_patents()
        elif choice == '5':
            _view_licenses()
        elif choice == '6':
            _add_license()
        elif choice == '7':
            _record_revenue()
        elif choice == '8' and is_admin:
            _create_patent()
        elif choice == '9' and is_admin:
            _update_patent_status()
        elif choice == '10' and is_admin:
            _portfolio_summary()
        else:
            print("Invalid choice.")


def _my_disclosures(user_id: str) -> None:
    """List the user's IP disclosures."""
    disclosures = IPManager.get_user_disclosures(user_id)
    print("\n" + "-" * 60)
    print("MY DISCLOSURES")
    print("-" * 60)

    if disclosures:
        for d in disclosures:
            print(f"\n  #{d.get('disclosure_id')}  {d.get('title', '')}")
            print(f"    Type: {(d.get('ip_type') or '').replace('_', ' ').title()}  |  "
                  f"Stage: {(d.get('development_stage') or '').replace('_', ' ').title()}  |  "
                  f"Status: {(d.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No disclosures.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _new_disclosure(user_id: str) -> None:
    """Create a new IP disclosure, optionally submitting it."""
    print("\n--- New IP Disclosure ---")
    title = input("Title: ").strip()
    if not title:
        print("\nTitle is required.")
        input("Press Enter to continue...")
        return

    ip_type = input("Type (invention/software/design/creative_work) [invention]: ").strip() or 'invention'
    description = input("Description: ").strip() or None
    stage = input("Development stage (concept/prototype/developed/commercial) [concept]: ").strip() or 'concept'
    funding_source = input("Funding source (optional): ").strip() or None

    try:
        disclosure_id = IPManager.create_disclosure(
            title=title, created_by=user_id, ip_type=ip_type,
            description=description, development_stage=stage,
            funding_source=funding_source,
        )
        print(f"\nDisclosure created (draft). ID: {disclosure_id}")

        # Optional co-inventors
        while input("Add a co-inventor? (y/n): ").strip().lower() == 'y':
            inv_user = input("  Co-inventor user ID: ").strip()
            if not inv_user:
                continue
            try:
                pct = float(input("  Contribution %: ").strip() or '0')
                IPManager.add_inventor(
                    disclosure_id=disclosure_id, user_id=inv_user,
                    contribution_percentage=pct,
                )
                print("  Co-inventor added.")
            except ValueError:
                print("  Invalid percentage; skipped.")

        submit = input("Submit disclosure for review now? (y/n): ").strip().lower()
        if submit == 'y':
            IPManager.submit_disclosure(disclosure_id)
            print("Disclosure submitted for review.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _submit_disclosure(user_id: str) -> None:
    """Submit a draft disclosure for review."""
    disclosures = IPManager.get_user_disclosures(user_id, status='draft')
    if not disclosures:
        print("\nNo draft disclosures to submit.")
        input("Press Enter to continue...")
        return

    for i, d in enumerate(disclosures, 1):
        print(f"  {i}. #{d.get('disclosure_id')}  {d.get('title', '')}")

    try:
        idx = int(input("\nSelect disclosure (0 to abort): ").strip())
        if 1 <= idx <= len(disclosures):
            IPManager.submit_disclosure(disclosures[idx - 1]['disclosure_id'])
            print("\nDisclosure submitted.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_patents() -> None:
    """List all patents."""
    patents = IPManager.get_patents()
    print("\n" + "-" * 60)
    print("PATENTS")
    print("-" * 60)

    if patents:
        for p in patents:
            print(f"\n  #{p.get('patent_id')}  {p.get('title', '')}")
            print(f"    Number: {p.get('patent_number') or 'N/A'}  |  "
                  f"Office: {p.get('patent_office', '')}  |  "
                  f"Status: {(p.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No patents.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_licenses() -> None:
    """List all licenses."""
    licenses = IPManager.get_licenses()
    print("\n" + "-" * 60)
    print("LICENSES")
    print("-" * 60)

    if licenses:
        for lic in licenses:
            print(f"\n  #{lic.get('license_id')}  {lic.get('licensee_name', '')}")
            print(f"    Type: {(lic.get('license_type') or '').replace('_', ' ').title()}  |  "
                  f"Royalty: {float(lic.get('royalty_rate', 0) or 0):.1f}%  |  "
                  f"Territory: {lic.get('territory', '')}  |  "
                  f"Status: {(lic.get('status') or '').title()}")
    else:
        print("\n  No licenses.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _pick_patent():
    """Prompt to select a patent. Returns patent_id or None (blank = no patent)."""
    patents = IPManager.get_patents()
    if not patents:
        return None
    print("\nPatents:")
    for i, p in enumerate(patents, 1):
        print(f"  {i}. #{p.get('patent_id')}  {p.get('title', '')}")
    choice = input("Select patent (blank for none): ").strip()
    if not choice:
        return None
    try:
        idx = int(choice)
        if 1 <= idx <= len(patents):
            return patents[idx - 1]['patent_id']
    except ValueError:
        pass
    return None


def _add_license() -> None:
    """Create a license agreement."""
    print("\n--- Add License ---")
    licensee = input("Licensee name: ").strip()
    if not licensee:
        print("\nLicensee name is required.")
        input("Press Enter to continue...")
        return

    patent_id = _pick_patent()
    lic_type = input("License type (exclusive/non_exclusive) [non_exclusive]: ").strip() or 'non_exclusive'
    start_date = input(f"Start date (YYYY-MM-DD) [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() \
        or datetime.now().strftime('%Y-%m-%d')
    territory = input("Territory [worldwide]: ").strip() or 'worldwide'

    try:
        royalty_rate = float(input("Royalty rate (%) [0]: ").strip() or '0')
        annual_fee = float(input("Annual fee [0]: ").strip() or '0')

        license_id = IPManager.create_license(
            licensee_name=licensee, start_date=start_date, patent_id=patent_id,
            license_type=lic_type, royalty_rate=royalty_rate,
            territory=territory, annual_fee=annual_fee,
        )
        print(f"\nLicense created. ID: {license_id}")
    except ValueError:
        print("\nInvalid numeric input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _record_revenue() -> None:
    """Record revenue for a license."""
    licenses = IPManager.get_licenses()
    if not licenses:
        print("\nNo licenses available.")
        input("Press Enter to continue...")
        return

    for i, lic in enumerate(licenses, 1):
        print(f"  {i}. #{lic.get('license_id')}  {lic.get('licensee_name', '')}")

    try:
        idx = int(input("\nSelect license (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(licenses)):
            return
        license_id = licenses[idx - 1]['license_id']

        period = input("Period (e.g. 2026-Q1): ").strip()
        if not period:
            print("\nPeriod is required.")
            input("Press Enter to continue...")
            return
        total_revenue = float(input("Total revenue: ").strip() or '0')
        uni_share = float(input("University share [0]: ").strip() or '0')
        inv_share = float(input("Inventor share [0]: ").strip() or '0')
        dept_share = float(input("Department share [0]: ").strip() or '0')

        revenue_id = IPManager.record_revenue(
            license_id=license_id, period=period, total_revenue=total_revenue,
            university_share=uni_share, inventor_share=inv_share,
            department_share=dept_share,
        )
        print(f"\nRevenue recorded. ID: {revenue_id}")
    except ValueError:
        print("\nInvalid numeric input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _create_patent() -> None:
    """Create a patent record (admin), optionally linked to a disclosure."""
    print("\n--- Create Patent ---")
    title = input("Title: ").strip()
    if not title:
        print("\nTitle is required.")
        input("Press Enter to continue...")
        return

    disclosure_input = input("Disclosure ID (optional): ").strip()
    patent_office = input("Patent office [USPTO]: ").strip() or 'USPTO'
    status = input("Status (pending/filed/published/granted) [pending]: ").strip() or 'pending'

    try:
        disclosure_id = int(disclosure_input) if disclosure_input else None
        patent_id = IPManager.create_patent(
            title=title, disclosure_id=disclosure_id,
            patent_office=patent_office, status=status,
        )
        print(f"\nPatent created. ID: {patent_id}")
    except ValueError:
        print("\nInvalid disclosure ID.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _update_patent_status() -> None:
    """Update the status of a patent (admin)."""
    patents = IPManager.get_patents()
    if not patents:
        print("\nNo patents available.")
        input("Press Enter to continue...")
        return

    for i, p in enumerate(patents, 1):
        print(f"  {i}. #{p.get('patent_id')}  {p.get('title', '')} [{p.get('status', '')}]")

    try:
        idx = int(input("\nSelect patent (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(patents)):
            return
        patent = patents[idx - 1]
        new_status = input("New status (pending/filed/published/granted): ").strip()
        if not new_status:
            print("\nStatus is required.")
            input("Press Enter to continue...")
            return
        IPManager.update_patent(patent['patent_id'], status=new_status)
        print(f"\nPatent status updated to '{new_status}'.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _portfolio_summary() -> None:
    """Display the IP portfolio summary (admin)."""
    print("\n" + "-" * 60)
    print("IP PORTFOLIO SUMMARY")
    print("-" * 60)
    try:
        summary = IPManager.get_portfolio_summary()
        disc = summary.get('disclosures_by_status', {})
        pat = summary.get('patents_by_status', {})
        print(f"\n  Total Disclosures: {sum(disc.values())}")
        for status, count in disc.items():
            print(f"    {status.replace('_', ' ').title()}: {count}")
        print("\n  Patents:")
        for status, count in pat.items():
            print(f"    {status.replace('_', ' ').title()}: {count}")
        print(f"\n  Active Licenses: {summary.get('active_licenses', 0)}")
        print(f"  Total Revenue: {float(summary.get('total_revenue', 0) or 0):,.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")

    print("-" * 60)
    input("\nPress Enter to continue...")
