"""Pure risk-scoring helpers.

No database access, no console I/O — safe to import and unit test on their own.
"""

import logging

def assess_contact_risk(contact, disease, severity):
    """Assess risk level for a contact based on exposure parameters"""
    risk_factors = 0

    # Contact type risk
    if contact['type'] == 'household':
        risk_factors += 3
    elif contact['type'] == 'close':
        risk_factors += 2
    elif contact['type'] == 'healthcare':
        risk_factors += 1

    # Duration risk
    try:
        duration = int(contact['duration'])
        if duration >= 60:
            risk_factors += 2
        elif duration >= 15:
            risk_factors += 1
    except (ValueError, KeyError, TypeError) as e:
        logging.warning(f"Invalid duration value in contact data: {e}")

    # Disease severity
    if severity in ['Severe', 'Critical']:
        risk_factors += 1

    # Disease type
    high_transmission_diseases = ['COVID-19', 'Influenza', 'Measles', 'Tuberculosis']
    if disease in high_transmission_diseases:
        risk_factors += 1

    # Risk classification
    if risk_factors >= 4:
        return 'High'
    elif risk_factors >= 2:
        return 'Moderate'
    else:
        return 'Low'


def calculate_risk_score(assessment_type, age, conditions, allergies, latest_bmi):
    """Calculate risk score based on assessment type and health data"""
    base_score = 0

    # Age-based risk
    if age >= 65:
        base_score += 20
    elif age >= 45:
        base_score += 10
    elif age >= 25:
        base_score += 5

    # Condition-based risk
    high_risk_conditions = ['diabetes', 'hypertension', 'heart disease', 'asthma', 'obesity']
    for condition_name, severity in conditions:
        if any(risk_condition in condition_name.lower() for risk_condition in high_risk_conditions):
            if severity == 'Severe':
                base_score += 15
            elif severity == 'Moderate':
                base_score += 10
            else:
                base_score += 5

    # BMI-based risk
    if latest_bmi:
        bmi = latest_bmi[0]
        if bmi >= 30:
            base_score += 15
        elif bmi >= 25:
            base_score += 10
        elif bmi < 18.5:
            base_score += 5

    # Allergy-based risk
    for allergen, severity in allergies:
        if severity in ['Severe', 'Life-threatening']:
            base_score += 10
        elif severity == 'Moderate':
            base_score += 5

    # Assessment-specific adjustments
    if assessment_type == 'Cardiovascular Risk':
        # Additional cardiovascular risk factors would be assessed here
        pass
    elif assessment_type == 'Mental Health Risk':
        # Mental health specific risk factors
        pass

    return min(base_score, 100)  # Cap at 100


def get_risk_factors(assessment_type, age, conditions, allergies, latest_bmi):
    """Get list of risk factors based on assessment"""
    risk_factors = []

    if age >= 65:
        risk_factors.append("Advanced age (65+)")
    elif age >= 45:
        risk_factors.append("Middle age (45-64)")

    for condition_name, severity in conditions:
        risk_factors.append(f"Medical condition: {condition_name} ({severity})")

    for allergen, severity in allergies:
        if severity in ['Severe', 'Life-threatening']:
            risk_factors.append(f"Severe allergy: {allergen}")

    if latest_bmi:
        bmi = latest_bmi[0]
        if bmi >= 30:
            risk_factors.append(f"Obesity (BMI: {bmi})")
        elif bmi >= 25:
            risk_factors.append(f"Overweight (BMI: {bmi})")
        elif bmi < 18.5:
            risk_factors.append(f"Underweight (BMI: {bmi})")

    return risk_factors


def generate_risk_recommendations(assessment_type, risk_score, risk_factors):
    """Generate recommendations based on risk assessment"""
    recommendations = []

    if risk_score >= 75:
        recommendations.append("Schedule immediate follow-up with healthcare provider")
        recommendations.append("Consider referral to specialist")
    elif risk_score >= 50:
        recommendations.append("Schedule follow-up within 30 days")
        recommendations.append("Implement risk reduction strategies")
    elif risk_score >= 25:
        recommendations.append("Schedule follow-up within 3 months")
        recommendations.append("Monitor risk factors")
    else:
        recommendations.append("Continue routine preventive care")
        recommendations.append("Annual reassessment recommended")

    # Assessment-specific recommendations
    if assessment_type == 'Cardiovascular Risk':
        recommendations.extend([
            "Regular blood pressure monitoring",
            "Cholesterol screening",
            "Heart-healthy diet and exercise"
        ])
    elif assessment_type == 'Mental Health Risk':
        recommendations.extend([
            "Mental health screening",
            "Stress management techniques",
            "Counseling services available"
        ])

    return recommendations
