# Course Evaluation Templates

This directory contains pre-configured evaluation templates that can be loaded into the Course Evaluation System.

## Available Templates

1. **Course Content Quality** - Evaluates relevance, organization, and depth of course content
2. **Instructor Effectiveness** - Assesses teaching methods, communication, and support
3. **Learning Outcomes Achievement** - Measures achievement of stated learning objectives
4. **Course Materials & Resources** - Evaluates quality of textbooks, slides, and materials
5. **Assessment & Grading** - Assesses fairness and clarity of exams and assignments
6. **Class Environment & Engagement** - Measures classroom atmosphere and participation
7. **Time Management & Workload** - Evaluates course pacing and workload appropriateness
8. **Technical Skills Development** - Assesses practical and technical skill development
9. **Communication & Feedback** - Evaluates instructor feedback quality and timeliness
10. **Overall Course Satisfaction** - General satisfaction and recommendation
11. **Laboratory & Practical Sessions** - Evaluates hands-on learning activities
12. **Online Learning Experience** - Assesses online tools and remote learning quality
13. **Group Work & Collaboration** - Evaluates collaborative learning opportunities
14. **Career Relevance & Application** - Measures real-world applicability
15. **Course Organization & Structure** - Assesses planning, syllabus, and schedule

## Template Structure

Each template is a JSON file with the following structure:

```json
{
  "template_name": "Template Name",
  "template_type": "Course|Instructor|Program|Custom",
  "description": "Description of what this template evaluates",
  "questions": [
    {
      "question_text": "The question text",
      "question_type": "Rating|Yes/No|Text|Multiple Choice",
      "question_category": "Course Content|Instructor|Materials|Assessment|General",
      "scale_min": 1,
      "scale_max": 5
    }
  ]
}
```

## Question Types

- **Rating**: Numeric scale (e.g., 1-5) for quantitative feedback
- **Yes/No**: Binary response for clear-cut questions
- **Text**: Free-form text response for qualitative feedback
- **Multiple Choice**: Select from predefined options

## Question Categories

- **Course Content**: Questions about syllabus, topics, and material
- **Instructor**: Questions about teaching effectiveness
- **Materials**: Questions about textbooks, slides, resources
- **Assessment**: Questions about exams, assignments, grading
- **General**: Questions about overall experience

## How to Use

1. Open the Course Evaluation GUI
2. Go to the "Templates" tab
3. Click "Load Template from File"
4. Select the template you want to import
5. Preview the questions
6. Click "Load Selected Template" to import into database

## Customization

You can:
- Modify existing templates by editing the JSON files
- Create new templates by copying and editing an existing file
- Mix and match questions from different templates
- Adjust scale ranges (e.g., 1-10 instead of 1-5)

## Notes

- Each template contains exactly 3 questions
- Templates are designed to be comprehensive yet concise
- Questions use a mix of quantitative (Rating) and qualitative (Text) formats
- All templates are ready to use out-of-the-box
- Templates can be combined for comprehensive evaluations
