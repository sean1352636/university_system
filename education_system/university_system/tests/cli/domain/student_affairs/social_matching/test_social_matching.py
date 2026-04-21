"""
Test script for Social Matching module.

Simple test to verify module functionality.
"""

import sys

from education_system.university_system.modules.domain.student_affairs.social_matching.services.social_matching_service import (
    SocialMatchingService,
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES
)


def test_basic_functionality():
    """Test basic functionality of the social matching service."""
    print("=" * 70)
    print("SOCIAL MATCHING MODULE TEST")
    print("=" * 70)

    # Initialize service
    print("\n1. Initializing Social Matching Service...")
    service = SocialMatchingService()
    print("   ✓ Service initialized successfully")

    # Test interest categories
    print("\n2. Testing Interest Categories...")
    print(f"   Available categories: {len(INTEREST_CATEGORIES)}")
    for category in INTEREST_CATEGORIES:
        print(f"     - {category}")
    print("   ✓ Interest categories loaded")

    # Test personality types
    print("\n3. Testing Personality Types...")
    print(f"   Available types: {len(PERSONALITY_TYPES)}")
    for ptype in PERSONALITY_TYPES:
        print(f"     - {ptype}")
    print("   ✓ Personality types loaded")

    # Test adding interests (mock user)
    print("\n4. Testing Interest Management...")
    test_user = "test_student_001"

    try:
        # Add interests
        service.add_user_interest(test_user, "Sports", "Basketball", 8, True)
        service.add_user_interest(test_user, "Music", "Rock", 7, True)
        service.add_user_interest(test_user, "Technology", "Programming", 9, True)
        print("   ✓ Added 3 interests successfully")

        # Get interests
        interests = service.get_user_interests(test_user)
        print(f"   ✓ Retrieved {len(interests)} interests")

        for interest in interests:
            print(f"     - {interest['category']}: {interest['name']} "
                  f"(Level: {interest['level']}/10)")

        # Remove interests
        for interest in interests:
            service.remove_user_interest(test_user, interest['interest_id'])
        print("   ✓ Removed all interests successfully")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test personality profile
    print("\n5. Testing Personality Profile...")
    try:
        service.set_personality_profile(
            test_user,
            personality_type="Extrovert",
            extroversion_score=8,
            openness_score=7,
            social_preference="Love meeting new people",
            group_size_pref="Medium Group (6-10)",
            activity_level="High"
        )
        print("   ✓ Created personality profile")

        profile = service.get_personality_profile(test_user)
        if profile:
            print(f"   ✓ Retrieved profile: {profile['personality_type']}, "
                  f"Extroversion: {profile['extroversion_score']}/10")
        else:
            print("   ✗ Failed to retrieve profile")
            return False

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test privacy settings
    print("\n6. Testing Privacy Settings...")
    try:
        service.set_privacy_settings(
            test_user,
            allow_matching=True,
            show_profile=True,
            allow_messages=True,
            show_interests=True,
            show_in_search=True
        )
        print("   ✓ Set privacy settings")

        settings = service.get_privacy_settings(test_user)
        print(f"   ✓ Retrieved settings: Allow Matching = {settings['allow_matching']}")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test statistics
    print("\n7. Testing Statistics...")
    try:
        stats = service.get_user_statistics(test_user)
        print(f"   ✓ Retrieved statistics:")
        print(f"     - Total Interests: {stats['total_interests']}")
        print(f"     - Total Matches: {stats['total_matches']}")
        print(f"     - Requests Sent: {stats['requests_sent']}")
        print(f"     - Teams Joined: {stats['teams_joined']}")
        print(f"     - Activities Joined: {stats['activities_joined']}")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test team creation
    print("\n8. Testing Team Formation...")
    try:
        team_id = service.create_team(
            creator_id=test_user,
            team_name="Test Basketball Team",
            sport_type="Basketball",
            team_size=5,
            skill_level="Intermediate",
            description="Test team for module verification"
        )
        print(f"   ✓ Created team (ID: {team_id})")

        teams = service.get_available_teams(sport_type="Basketball")
        print(f"   ✓ Found {len(teams)} basketball team(s)")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test club recommendations
    print("\n9. Testing Club Recommendations...")
    try:
        # Add some interests first
        service.add_user_interest(test_user, "Sports", "Basketball", 8, True)
        service.add_user_interest(test_user, "Technology", "Programming", 9, True)

        recommendations = service.generate_club_recommendations(test_user)
        print(f"   ✓ Generated {len(recommendations)} recommendations")

        if recommendations:
            print("   Top 3 recommendations:")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"     {i}. {rec['club_name']} (Score: {rec['match_score']})")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)
    print("\nThe Social Matching module is ready to use.")
    print("\nTo use the module:")
    print("  - CLI: python -m university_system.modules.domain.student_affairs.social_matching.cli.social_matching_cli")
    print("  - GUI: python -m university_system.modules.domain.student_affairs.social_matching.gui.social_matching_gui")
    print("\nOr import in your code:")
    print("  from education_system.university_system.modules.domain.student_affairs.social_matching.import SocialMatchingService")

    return True


if __name__ == "__main__":
    try:
        success = test_basic_functionality()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
