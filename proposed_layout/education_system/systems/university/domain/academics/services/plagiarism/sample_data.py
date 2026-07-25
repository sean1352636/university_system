import os
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

logger = configure_logging(name=__name__)


def create_sample_documents(checker):
    """Create sample documents for testing the plagiarism system"""
    try:
        # Only create if directory is empty
        text_files_dir = 'text_files'
        if os.path.exists(text_files_dir) and not os.listdir(text_files_dir):
            print("\nCreating sample documents for testing...")

            # Get system users and modules
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Get users
                    cursor.execute('''
                    SELECT id, username FROM users
                    WHERE id IN (SELECT user_id FROM user_roles WHERE role_id IN
                        (SELECT id FROM roles WHERE role_name IN ('student', 'instructor', 'staff')))
                    LIMIT 3
                    ''')

                    users = cursor.fetchall()

                    # Get modules
                    cursor.execute('SELECT module_code FROM modules LIMIT 2')
                    modules = [row[0] for row in cursor.fetchall()]

                    if not users:
                        print("Warning: No suitable users found for creating sample documents.")
                        return

                    if not modules:
                        modules = ['TEST_MODULE']  # Fallback module

            except sqlite3.Error as e:
                print(f"Database error getting users/modules: {e}")
                return

            # Create sample documents with realistic content
            sample_docs = [
                {
                    'title': 'AI in Education: Opportunities and Challenges',
                    'content': create_ai_education_content(),
                    'filename': 'original_paper.txt'
                },
                {
                    'title': 'Artificial Intelligence Applications in Modern Education',
                    'content': create_similar_ai_content(),
                    'filename': 'similar_paper.txt'
                },
                {
                    'title': 'Environmental Impact of Urban Renewable Energy Transitions',
                    'content': create_different_content(),
                    'filename': 'different_paper.txt'
                }
            ]

            # Write files and add to repository
            for i, doc in enumerate(sample_docs):
                try:
                    # Write to file
                    file_path = os.path.join(text_files_dir, doc['filename'])
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(doc['content'])

                    # Add to repository
                    user_id = users[min(i, len(users)-1)][0]
                    module_code = modules[min(i, len(modules)-1)]

                    checker.add_document_to_repository(
                        doc['title'],
                        doc['content'],
                        user_id,
                        module_code,
                        'txt'
                    )

                    logger.info(f"Created sample document: {doc['title']}")

                except Exception as e:
                    logger.error(f"Error creating sample document {doc['title']}: {e}")

            print("Sample documents created and added to repository.")
            print("Test files are available in the 'text_files' directory.")

    except Exception as e:
        logger.error(f"Error creating sample documents: {e}")


def create_ai_education_content():
    """Create original AI education content"""
    return """
    Abstract
    This paper explores the growing importance of artificial intelligence in modern education.
    The integration of AI technologies in educational settings presents both opportunities and challenges.
    We analyze current trends and propose frameworks for ethical implementation.

    Introduction
    Artificial intelligence has transformed many sectors of society, and education is increasingly
    affected by these technological advances. From personalized learning to administrative efficiency,
    AI offers numerous benefits to educational institutions. However, concerns regarding privacy,
    algorithmic bias, and the changing role of educators require careful consideration.

    Literature Review
    Previous research has identified several key areas where AI impacts education.
    Smith (2020) explored how machine learning algorithms can predict student performance.
    Jones and Williams (2021) examined the ethical implications of automated assessment systems.
    Chen et al. (2022) investigated the role of natural language processing in providing
    feedback on student writing.

    Methodology
    Our study employed a mixed-methods approach, combining quantitative analysis of
    implementation outcomes across 42 educational institutions with qualitative
    interviews of 15 administrators, 30 teachers, and 50 students.

    Results
    The findings indicate that institutions implementing AI-assisted learning tools
    saw a 23% improvement in student engagement metrics and a 17% increase in
    completion rates for online courses. However, 68% of educators expressed
    concerns about reduced human interaction in the learning process.

    Discussion
    While the quantitative benefits of AI in education are clear, the qualitative
    concerns raised by stakeholders suggest that a balanced approach is necessary.
    The technology should augment rather than replace human teaching elements.

    Conclusion
    As AI continues to evolve, educational institutions must develop thoughtful
    integration strategies that maximize benefits while mitigating potential drawbacks.
    Future research should focus on longitudinal studies examining the long-term
    impacts of AI-assisted education on student outcomes and wellbeing.
    """


def create_similar_ai_content():
    """Create similar AI education content (for plagiarism testing)"""
    return """
    Abstract
    This paper examines the increasing significance of artificial intelligence in modern education.
    The adoption of AI technologies in educational contexts offers both opportunities and challenges.
    We examine current patterns and suggest frameworks for ethical implementation.

    Introduction
    Artificial intelligence has revolutionized many sectors of society, and education is increasingly
    influenced by these technological advances. From personalized learning to administrative efficiency,
    AI provides numerous advantages to educational institutions. However, issues regarding privacy,
    algorithmic bias, and the changing role of teachers require careful consideration.

    Literature Review
    Prior studies have identified several key areas where AI impacts education.
    Smith (2020) explored how machine learning algorithms can predict student performance.
    Jones and Williams (2021) examined the ethical implications of automated assessment systems.
    Chen et al. (2022) investigated the role of natural language processing in providing
    feedback on student writing.

    Methodology
    Our investigation used a mixed-methods approach, combining quantitative analysis of
    implementation outcomes across 42 schools with qualitative
    interviews of 15 administrators, 30 teachers, and 50 students.

    Results
    The data indicates that institutions implementing AI-assisted learning tools
    saw a 23% improvement in student engagement metrics and a 17% increase in
    completion rates for online courses. However, 68% of educators expressed
    concerns about reduced human interaction in the learning process.

    Discussion
    While the quantitative benefits of AI in education are evident, the qualitative
    concerns raised by participants suggest that a balanced approach is necessary.
    The technology should augment rather than replace human teaching elements.

    Conclusion
    As AI continues to develop, educational institutions must create thoughtful
    integration strategies that maximize benefits while minimizing potential drawbacks.
    Future research should focus on longitudinal studies examining the long-term
    effects of AI-assisted education on student outcomes and wellbeing.
    """


def create_different_content():
    """Create different content (for negative testing)"""
    return """
    Abstract
    This study investigates the environmental impact of renewable energy transitions in urban settings.
    With increasing concerns about climate change, cities worldwide are implementing sustainable
    energy solutions. We evaluate the effectiveness of these initiatives across different regions.

    Introduction
    Climate change presents an urgent challenge that requires significant transformations
    in how we produce and consume energy. Urban areas, responsible for over 70% of global
    carbon emissions, are critical sites for implementing renewable energy solutions.
    This paper examines various approaches cities have taken to reduce their carbon footprint.

    Literature Review
    Research on urban energy transitions has grown substantially in recent years.
    Wang (2021) analyzed solar panel adoption rates in metropolitan areas.
    Rodriguez and Lee (2022) compared the effectiveness of municipal incentive programs.
    The Urban Climate Initiative (2023) published comprehensive guidelines for city planners.

    Methodology
    We conducted case studies of five major cities across three continents,
    collecting data on energy consumption patterns, renewable infrastructure development,
    and policy frameworks. Interviews with 25 city officials and 10 energy experts
    provided additional insights into implementation challenges.

    Results
    Cities that integrated renewable energy planning with broader urban development
    goals achieved 34% greater emissions reductions than those implementing isolated
    initiatives. Public-private partnerships increased project completion rates by 28%.
    Community engagement programs correlated with 45% higher resident satisfaction.

    Discussion
    While technological solutions are important, our findings highlight the critical
    role of policy coherence and stakeholder engagement. Small-scale, community-based
    projects often serve as effective catalysts for larger transitions.

    Conclusion
    Successful urban energy transitions require integrated approaches that address
    technical, economic, and social dimensions simultaneously. Future research should
    explore how digital technologies might further optimize renewable energy systems
    in increasingly complex urban environments.
    """
