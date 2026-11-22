from datetime import datetime, timedelta


def health_challenges(auth):
    """Health challenges and competitions"""
    print("\n===== Health Challenges =====")

    challenges = [
        {
            "name": "10,000 Steps Challenge",
            "description": "Walk 10,000 steps daily for 30 days",
            "duration": "30 days",
            "participants": 150,
            "reward": "Fitness tracker discount"
        },
        {
            "name": "Hydration Challenge",
            "description": "Drink 8 glasses of water daily",
            "duration": "14 days",
            "participants": 89,
            "reward": "Water bottle prize"
        },
        {
            "name": "Mental Health Week",
            "description": "Daily mindfulness activities",
            "duration": "7 days",
            "participants": 234,
            "reward": "Wellness workshop access"
        },
        {
            "name": "Nutrition Challenge",
            "description": "5 servings of fruits/vegetables daily",
            "duration": "21 days",
            "participants": 67,
            "reward": "Healthy cooking class"
        }
    ]

    print("Current Active Challenges:")
    for i, challenge in enumerate(challenges):
        print(f"\n{i+1}. {challenge['name']}")
        print(f"   Description: {challenge['description']}")
        print(f"   Duration: {challenge['duration']}")
        print(f"   Participants: {challenge['participants']}")
        print(f"   Reward: {challenge['reward']}")

    if auth.current_user['role'] == 'student':
        join_challenge = input("\nJoin a challenge? (enter number or 'n'): ")
        if join_challenge.isdigit() and 1 <= int(join_challenge) <= len(challenges):
            selected_challenge = challenges[int(join_challenge) - 1]
            print(f"\nYou've joined the {selected_challenge['name']}!")
            print("Check your progress in the wellness tracking section.")



