"""Analytics in the CLI (over the readings on your modules)."""

from education_system.systems.university.shell.cli.ai.ai_detector import _cli


def _get_ai_detector():
    return _cli.detector()


def _report(method, title, *args, **kwargs):
    _cli.run(getattr(_get_ai_detector(), method), *args, title=title, **kwargs)
    _cli.pause()


def show_confidence_distribution_cli():
    _report("show_detection_confidence_distribution", "Spread of strengths")


def generate_word_cloud_cli():
    _report("generate_word_cloud", "Frequent words")


def plot_submission_timeline_cli():
    _report("plot_submission_timeline", "Readings over time")


def show_correlation_matrix_cli():
    _report("show_correlation_matrix", "How the indicators relate")


def cluster_similar_submissions_cli():
    _report("cluster_similar_submissions", "Very similar texts")


def generate_department_comparison_cli():
    _report("generate_department_comparison", "By module")


def show_weekly_trends_cli():
    _report("show_weekly_trends", "Week by week")


def export_visualization_pack_cli():
    _report("export_visualization_pack", "Data pack")
