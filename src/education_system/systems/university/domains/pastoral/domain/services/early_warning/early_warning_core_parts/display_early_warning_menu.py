"""Extracted function implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_early_warning_menu(auth):
    """Display the Student Success Early Warning System CLI menu"""
    print("\n" + "="*50)
    print(f" {_t('early_warning.cli.title', default='STUDENT SUCCESS EARLY WARNING SYSTEM')}")
    print("="*50)
    print(f"1. {_t('early_warning.cli.menu.at_risk', default='View At-Risk Students')}")
    print(f"2. {_t('early_warning.cli.menu.dashboard', default='Risk Assessment Dashboard')}")
    print(f"3. {_t('early_warning.cli.menu.intervention', default='Create Intervention Plan')}")
    print(f"4. {_t('early_warning.cli.menu.coach', default='Assign Success Coach')}")
    print(f"5. {_t('early_warning.cli.menu.progress', default='Track Student Progress')}")
    print(f"6. {_t('early_warning.cli.menu.tutoring', default='Tutoring Recommendations')}")
    print(f"7. {_t('early_warning.cli.menu.alerts', default='Send Alert Notifications')}")
    print(f"8. {_t('early_warning.cli.menu.language', default='Language')}")
    print(f"9. {_t('early_warning.cli.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{_t('early_warning.cli.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n{_t('early_warning.cli.feature_available', default='Feature available via Early Warning managers')}")
                print("Use: from education_system.systems.university.domains.pastoral.domain.services.early_warning import RiskAssessmentManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                print(_t('early_warning.cli.returning', default='Returning to main menu...'))
                break
            else:
                print(_t('early_warning.cli.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(_t('early_warning.cli.error', default='Error: {error}').format(error=e))
