"""AI-Powered Features console menu (over ``shared/ai/features``)."""


def display_ai_features_menu(auth):
    """Display the AI-Powered Features CLI menu"""
    print("\n" + "="*50)
    print("        AI-POWERED FEATURES")
    print("="*50)
    print("1. AI Chatbot")
    print("2. Recommendation Engine")
    print("3. Auto-Grading System")
    print("4. Content Suggestions")
    print("5. Sentiment Analysis")
    print("6. Plagiarism Detection")
    print("7. AI Model Performance")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice == '6':
                from education_system.systems.university.shell.cli.integrity_menu import (
                    integrity_menu,
                )
                integrity_menu(auth)
            elif choice in ['1', '2', '3', '4', '5', '7']:
                print("\n🤖 Feature available via AI managers")
                print("Use: from education_system.systems.university.shared.ai.features import ChatbotManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            break
