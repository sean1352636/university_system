# Machine Learning Infrastructure

Advanced ML/AI capabilities for the University Management System.

## Features Overview

### 1. Course Recommendation Engine

Personalized course recommendations using multiple algorithms:

**Algorithms:**
- **Collaborative Filtering**: Recommends based on similar students' choices
- **Content-Based Filtering**: Matches courses to student interests/major
- **Performance-Based**: Predicts success probability for each course
- **Popularity-Based**: Considers course ratings and enrollment

**Usage:**
```python
from university_system.infrastructure.ml import get_course_recommender

recommender = get_course_recommender()
recommendations = recommender.recommend_courses(
    student_id="student123",
    num_recommendations=10,
    filters={'department': 'Computer Science'}
)

for rec in recommendations:
    print(f"{rec.course_name}: Score {rec.score:.2f}")
    print(f"  Success Probability: {rec.success_probability:.1%}")
    print(f"  Reasoning: {', '.join(rec.reasoning)}")
```

**API Endpoint:**
```bash
curl -X POST http://localhost:8000/api/v1/ml/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "student123",
    "num_recommendations": 10
  }'
```

### 2. Automated Essay Grading

NLP-based essay analysis and grading with detailed feedback.

**Grading Dimensions:**
- **Content** (40%): Relevance, depth, keyword coverage
- **Organization** (25%): Structure, paragraphs, transitions
- **Grammar** (20%): Mechanics, sentence structure, spelling
- **Vocabulary** (15%): Diversity, academic words, style

**Usage:**
```python
from university_system.infrastructure.ml import get_essay_grader, GradingRubric

grader = get_essay_grader()

rubric = GradingRubric(
    total_points=100,
    min_words=250,
    max_words=1000,
    required_keywords=['climate', 'evidence', 'action']
)

feedback = grader.grade_essay(essay_text, rubric)

print(f"Score: {feedback.score}/{rubric.total_points}")
print(f"Strengths: {feedback.strengths}")
print(f"Suggestions: {feedback.suggestions}")
```

**API Endpoint:**
```bash
curl -X POST http://localhost:8000/api/v1/ml/grade-essay \
  -H "Content-Type: application/json" \
  -d '{
    "essay_text": "...",
    "total_points": 100,
    "min_words": 250,
    "required_keywords": ["keyword1", "keyword2"]
  }'
```

### 3. Advanced Plagiarism Detection

Detects plagiarism in text and code with similarity analysis.

**Features:**
- Text similarity using SequenceMatcher
- Code plagiarism detection (Python, Java, etc.)
- Multiple match types: exact, paraphrase, structural
- Severity classification: low, medium, high, critical

**Usage:**
```python
from university_system.infrastructure.ml import get_plagiarism_detector

detector = get_plagiarism_detector()

sources = [
    {"name": "Source A", "content": "Original text..."},
    {"name": "Source B", "content": "Another source..."}
]

result = detector.check_plagiarism(
    text="Student submission...",
    sources=sources,
    threshold=0.3
)

if result['is_plagiarized']:
    for match in result['matches']:
        print(f"Match: {match.matched_source}")
        print(f"  Similarity: {match.similarity_score:.1%}")
        print(f"  Severity: {match.severity}")
```

**Code Plagiarism:**
```python
from university_system.infrastructure.ml import CodePlagiarismDetector

detector = CodePlagiarismDetector()

result = detector.check_code_plagiarism(
    code="student_code.py content",
    sources=[{"name": "reference.py", "content": "..."}],
    language="python"
)
```

### 4. Predictive Analytics

Predicts student success and identifies at-risk students.

**Predictions:**
- Future GPA based on current performance
- Graduation probability
- Risk factor identification
- Personalized recommendations

**Usage:**
```python
from university_system.infrastructure.ml import get_success_predictor

predictor = get_success_predictor()

prediction = predictor.predict_success(
    student_id="student123",
    current_gpa=3.2,
    credits_completed=60,
    attendance_rate=0.85
)

print(f"Predicted GPA: {prediction.predicted_gpa}")
print(f"Graduation Probability: {prediction.graduation_probability:.1%}")
print(f"At Risk: {prediction.at_risk}")

if prediction.at_risk:
    print(f"Risk Factors: {prediction.risk_factors}")
    print(f"Recommendations: {prediction.recommendations}")
```

**API Endpoint:**
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict-success \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "student123",
    "current_gpa": 3.2,
    "credits_completed": 60,
    "attendance_rate": 0.85
  }'
```

### 5. Learning Path Optimization

Generates optimized course sequences for degree completion.

**Path Types:**
- **Balanced**: Standard workload, moderate difficulty
- **Accelerated**: Higher workload, faster completion
- **Specialized**: Focus on specific area of study

**Usage:**
```python
from university_system.infrastructure.ml import get_path_optimizer

optimizer = get_path_optimizer()

paths = optimizer.optimize_path(
    student_id="student123",
    goal="Computer Science Degree",
    current_courses=[],
    target_graduation_semesters=8
)

for path in paths:
    print(f"{path.path_id.upper()} Path:")
    print(f"  Duration: {path.estimated_duration_semesters} semesters")
    print(f"  Difficulty: {path.difficulty_rating:.1f}/1.0")
    print(f"  Success Probability: {path.success_probability:.1%}")
    print(f"  Reasoning: {', '.join(path.reasoning)}")
```

## Installation

### Required Dependencies

Basic NLP (included in requirements.txt):
```bash
pip install nltk
python -m nltk.downloader punkt stopwords
```

### Optional (for enhanced features):

**Advanced ML:**
```bash
pip install scikit-learn numpy
```

**Deep Learning (best accuracy):**
```bash
# Install PyTorch
pip install torch torchvision torchaudio

# Or TensorFlow
pip install tensorflow
```

**Advanced NLP:**
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

## API Reference

All ML endpoints are under `/api/v1/ml/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recommendations` | POST | Get course recommendations |
| `/grade-essay` | POST | Grade an essay |
| `/check-plagiarism` | POST | Check for plagiarism |
| `/predict-success` | POST | Predict student success |
| `/optimize-path/{student_id}` | POST | Optimize learning path |

## Integration Examples

### Integrate with Grade Posting

```python
from university_system.infrastructure.ml import get_essay_grader, GradingRubric

def grade_student_essay(student_id, essay_text):
    grader = get_essay_grader()

    rubric = GradingRubric(
        total_points=100,
        min_words=500,
        required_keywords=['thesis', 'evidence', 'conclusion']
    )

    # Auto-grade essay
    feedback = grader.grade_essay(essay_text, rubric)

    # Save to database
    save_grade(student_id, feedback.score)

    # Send feedback to student
    send_feedback(student_id, feedback)

    return feedback
```

### Integrate with Enrollment

```python
from university_system.infrastructure.ml import get_course_recommender

def help_student_select_courses(student_id):
    recommender = get_course_recommender()

    # Get personalized recommendations
    recommendations = recommender.recommend_courses(
        student_id=student_id,
        num_recommendations=10
    )

    # Display to student with reasoning
    for rec in recommendations:
        print(f"Recommended: {rec.course_name}")
        print(f"  Why: {', '.join(rec.reasoning)}")
        print(f"  Success Rate: {rec.success_probability:.1%}")

    return recommendations
```

### Early Warning System

```python
from university_system.infrastructure.ml import get_success_predictor

def identify_at_risk_students():
    predictor = get_success_predictor()

    students = get_all_students()
    at_risk_students = []

    for student in students:
        prediction = predictor.predict_success(
            student_id=student['id'],
            current_gpa=student['gpa'],
            credits_completed=student['credits'],
            attendance_rate=student['attendance']
        )

        if prediction.at_risk:
            at_risk_students.append({
                'student': student,
                'prediction': prediction
            })

            # Alert advisor
            notify_advisor(student['advisor_id'], prediction)

    return at_risk_students
```

## Model Training

### Train Recommendation Model

```python
from university_system.infrastructure.ml import get_course_recommender

recommender = get_course_recommender()

# Train on historical data
recommender.train_model()

# Model automatically loads student profiles and enrollment history
```

### Custom Models

To add custom ML models:

1. Create model class in `infrastructure/ml/`
2. Implement training and prediction methods
3. Add API endpoint in `api/routes/ml/main.py`
4. Update `__init__.py` exports

Example:
```python
# infrastructure/ml/custom_model.py
class CustomPredictor:
    def __init__(self):
        self.model = None

    def train(self, data):
        # Training logic
        pass

    def predict(self, features):
        # Prediction logic
        pass
```

## Performance Considerations

- **In-Memory**: Models use in-memory storage by default
- **Database**: Can be configured to use database for persistence
- **Caching**: Student profiles are cached for better performance
- **Batch Processing**: Support for batch predictions

## Testing

Run ML demos:
```bash
source venv/bin/activate
export APP_ENV=development
python examples/ml_demo.py
```

## Limitations & Future Improvements

### Current Limitations:
- Simplified collaborative filtering (can be enhanced with matrix factorization)
- Basic NLP features (can be upgraded to transformer models)
- No GPU acceleration (CPU-only inference)
- Limited training data handling

### Planned Improvements:
- [ ] Deep learning models for better accuracy
- [ ] Real-time model training and updates
- [ ] GPU acceleration support
- [ ] Advanced NLP with BERT/GPT integration
- [ ] Multi-modal learning (text + images)
- [ ] Explainable AI features
- [ ] A/B testing framework
- [ ] Model versioning and rollback

## Ethical Considerations

### AI Ethics Guidelines:
1. **Transparency**: Students should know when AI is grading/recommending
2. **Human Oversight**: AI should assist, not replace human judgment
3. **Fairness**: Monitor for bias in recommendations and predictions
4. **Privacy**: Student data used for ML must be protected
5. **Consent**: Students should consent to AI analysis of their work

### Bias Mitigation:
- Regular model audits for fairness
- Diverse training data
- Human review of AI decisions
- Opt-out options for students

## Support

For issues or questions:
- Check documentation: `infrastructure/ml/README.md`
- Run demos: `examples/ml_demo.py`
- API docs: http://localhost:8000/docs
- Report issues: GitHub issues

## License

Same as main University Management System project.
