"""Flask REST API for enhanced reporting."""

import os
import secrets
from datetime import datetime, timedelta

from education_system.university_system.modules.shared.services.analytics.enhanced_reporting._compat import Flask, request, jsonify
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.config import CONFIG, AVAILABLE_SECTIONS, get_reporting_db_connection, serialize_dataframe, logger
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.models import ReportTemplate
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.data_quality import DataQualityMonitor
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.predictive import PredictiveAnalytics

# Flask app for REST API
app = Flask(__name__)
app.secret_key = CONFIG['secret_key']

# Initialize security headers for all responses
try:
    from education_system.university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_reporting_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0',
            'database': 'connected'
        })
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return jsonify({
            'status': 'unhealthy',
            'error': 'Internal server error',
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/data/<section>', methods=['GET'])
def api_get_section_data(section):
    """Get data for a specific section"""
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.data_retrieval import get_section_dataframe

    try:
        if section not in AVAILABLE_SECTIONS:
            return jsonify({'error': 'Invalid section'}), 400

        # Get date parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")

        # Get data
        df = get_section_dataframe(section, start_date, end_date, {})
        data = serialize_dataframe(df)

        return jsonify({
            'section': section,
            'data': data,
            'start_date': start_date,
            'end_date': end_date,
            'record_count': len(data)
        })

    except Exception as e:
        logger.error("API get section data error: %s", e)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/templates', methods=['GET'])
def api_get_templates():
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.templates_db import load_templates
    templates = load_templates()
    return jsonify(templates)


@app.route('/api/templates', methods=['POST'])
def api_create_template():
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.templates_db import save_template
    data = request.get_json()

    template = ReportTemplate(
        name=data['name'],
        description=data['description'],
        sections=data['sections'],
        filters=data.get('filters', {}),
        visualization_type=data.get('visualization_type', 'standard'),
        security_level=data.get('security_level', 'normal')
    )

    saved_template = save_template(template)
    return jsonify(saved_template.to_dict())


@app.route('/api/reports/generate', methods=['POST'])
def api_generate_report():
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.templates_db import get_template
    from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.report_generation import generate_report

    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        template_name = data.get('template_name')
        if not template_name:
            return jsonify({'error': 'template_name is required'}), 400

        # Verify template exists
        template = get_template(template_name)
        if not template:
            return jsonify({'error': 'Template not found'}), 404

        start_date = data.get('start_date')
        end_date = data.get('end_date')
        output_format = data.get('format', 'pdf')

        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")

        report_path = generate_report(template_name, start_date, end_date, output_format)

        if report_path:
            return jsonify({
                'success': True,
                'report_path': report_path,
                'message': 'Report generated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to generate report'}), 500

    except Exception as e:
        logger.error("API generate report error: %s", e)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@app.route('/api/analytics/quality', methods=['GET'])
def api_data_quality():
    quality_report = DataQualityMonitor.run_quality_checks()
    return jsonify(quality_report)


@app.route('/api/analytics/predictions', methods=['GET'])
def api_predictions():
    predictions = PredictiveAnalytics.predict_dropout_risk()
    return jsonify(predictions)


@app.route('/api/analytics/anomalies', methods=['GET'])
def api_anomalies():
    anomalies = PredictiveAnalytics.detect_anomalies()
    return jsonify(anomalies)
