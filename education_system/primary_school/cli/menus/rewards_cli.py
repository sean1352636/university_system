"""Rewards CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def rewards_menu(auth):
    """Rewards management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pastoral_care.rewards.services.rewards_service import RewardsService

    svc = RewardsService(get_db_path())

    while True:
        print_header("Rewards")
        print_menu([
            ("1", "List rewards"),
            ("2", "View details"),
            ("3", "Add Reward"),
            ("4", "Update Reward"),
            ("5", "Delete Reward"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_rewards()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_reward(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            reward_type = input("  Reward Type: ").strip()
            try:
                svc.create_reward(pupil_id=pupil_id, reward_type=reward_type)
                print("\n  Reward created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            reward_type = input("  Reward Type: ").strip()
            try:
                svc.update_reward(int(pk), pupil_id=pupil_id, reward_type=reward_type)
                print("\n  Reward updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_reward(int(pk))
                print("\n  Reward deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
