"""Optional dependency handling for the enhanced reporting package.

Many of the analytics features rely on third-party libraries such as pandas,
numpy, matplotlib, seaborn, plotly, schedule, reportlab, Flask and
scikit-learn.  In lightweight environments where these packages are not
installed we still want to be able to import this package without errors.
The following blocks attempt to import each optional dependency.  If the
import fails a minimal shim is created so that references to the module
will not raise attribute errors.
"""

import logging
import warnings

# ── pandas ──────────────────────────────────────────────────────────────────
try:
    import pandas as pd  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    class _Dummy:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):
            return None
        def __iter__(self):
            return iter([])
    pd = _Dummy()  # type: ignore

# ── numpy ───────────────────────────────────────────────────────────────────
try:
    import numpy as np  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    class _NumPyDummy:
        def __getattr__(self, name):
            def _no_op(*args, **kwargs):
                return None
            return _no_op
        def array(self, *args, **kwargs):
            return []
    np = _NumPyDummy()  # type: ignore

# ── matplotlib and seaborn ──────────────────────────────────────────────────
try:
    import matplotlib.pyplot as plt  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    class _MatPlotDummy:
        def __getattr__(self, name):
            def _no_op(*args, **kwargs):
                return None
            return _no_op
    plt = _MatPlotDummy()  # type: ignore
try:
    import seaborn as sns  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    class _SeabornDummy:
        def __getattr__(self, name):
            def _no_op(*args, **kwargs):
                return None
            return _no_op
    sns = _SeabornDummy()  # type: ignore

# ── plotly ──────────────────────────────────────────────────────────────────
try:
    import plotly.graph_objects as go  # type: ignore
    import plotly.express as px  # type: ignore
    import plotly.offline as pyo  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    class _PlotlyDummy:
        def __getattr__(self, name):
            def _no_op(*args, **kwargs):
                return None
            return _no_op
        def __call__(self, *args, **kwargs):
            return None
    go = _PlotlyDummy()  # type: ignore
    px = _PlotlyDummy()  # type: ignore
    pyo = _PlotlyDummy()  # type: ignore

# ── schedule ────────────────────────────────────────────────────────────────
try:
    import schedule  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")

    class _ScheduleJobStub:
        """
        Stub implementation for schedule.Job when schedule library is not available.

        This stub allows the code to run without the schedule library installed,
        but scheduled tasks will not actually execute. All method calls return self
        to support method chaining, and job functions are stored but never executed.

        Attributes:
            _jobs (list): List of registered job functions
            _interval (int): Interval value for scheduling
            _unit (str): Time unit for scheduling (seconds, minutes, hours, etc.)
            _at_time (str): Specific time for scheduling
            _tag (str): Tag identifier for the job
        """

        def __init__(self, *args, **kwargs):
            """Initialize the stub with tracking attributes."""
            self._jobs = []
            self._interval = None
            self._unit = None
            self._at_time = None
            self._tag = None
            self._args = args
            self._kwargs = kwargs
            warnings.warn(
                "schedule library not installed. Scheduled tasks will not execute. "
                "Install with: pip install schedule",
                RuntimeWarning
            )

        def do(self, job_func, *args, **kwargs):
            """
            Store the job function but do not schedule it.

            Args:
                job_func: The function to be scheduled
                *args: Positional arguments for the job function
                **kwargs: Keyword arguments for the job function

            Returns:
                self: For method chaining
            """
            self._jobs.append({
                'function': job_func,
                'args': args,
                'kwargs': kwargs,
                'interval': self._interval,
                'unit': self._unit,
                'at_time': self._at_time,
                'tag': self._tag
            })
            logging.debug(
                f"Job '{job_func.__name__}' registered in stub (will not execute). "
                f"Interval: {self._interval} {self._unit}"
            )
            return self

        def at(self, time_str):
            """Set the time for job execution."""
            self._at_time = time_str
            return self

        def tag(self, *tags):
            """Add tags to the job."""
            self._tag = tags
            return self

        def until(self, *args, **kwargs):
            """Set end time for job execution."""
            return self

        def __getattr__(self, name):
            """
            Handle unknown attributes by setting unit and returning self.
            This supports schedule's fluent API like .seconds, .minutes, etc.
            """
            if name in ('second', 'seconds', 'minute', 'minutes', 'hour', 'hours',
                       'day', 'days', 'week', 'weeks', 'monday', 'tuesday',
                       'wednesday', 'thursday', 'friday', 'saturday', 'sunday'):
                self._unit = name
                return self
            return self

        def __call__(self, *args, **kwargs):
            """Support callable behavior for compatibility."""
            return self

    class schedule:  # type: ignore
        """
        Stub implementation for schedule module when not available.

        This stub provides the schedule module's API without actual scheduling
        functionality. It's used to prevent import errors when schedule is not installed.
        """

        _jobs = []  # Class-level job tracking

        @staticmethod
        def every(interval=1):
            """
            Create a new job stub with the specified interval.

            Args:
                interval (int): The interval value for scheduling

            Returns:
                _ScheduleJobStub: A job stub instance
            """
            job = _ScheduleJobStub()
            job._interval = interval
            schedule._jobs.append(job)
            return job

        @staticmethod
        def run_pending():
            """
            Stub for running pending jobs. Does nothing but logs a warning.

            In the real schedule library, this would execute any pending jobs.
            """
            if schedule._jobs:
                logging.debug(
                    f"run_pending() called on stub with {len(schedule._jobs)} registered jobs. "
                    "No jobs executed (schedule library not installed)."
                )
            return None

        @staticmethod
        def clear(tag=None):
            """Clear all jobs or jobs with a specific tag."""
            if tag:
                schedule._jobs = [j for j in schedule._jobs if getattr(j, '_tag', None) != tag]
            else:
                schedule._jobs = []
            return None

        @staticmethod
        def get_jobs(tag=None):
            """Get all scheduled jobs or jobs with a specific tag."""
            if tag:
                return [j for j in schedule._jobs if getattr(j, '_tag', None) == tag]
            return schedule._jobs.copy()

        @staticmethod
        def cancel_job(job):
            """Cancel a specific job."""
            if job in schedule._jobs:
                schedule._jobs.remove(job)
            return None

# ── reportlab ───────────────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import letter, A4  # type: ignore
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
    from reportlab.lib import colors  # type: ignore
    from reportlab.lib.units import inch  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    warnings.warn(
        "reportlab library not installed. PDF generation will not work. "
        "Install with: pip install reportlab",
        RuntimeWarning
    )

    # Provide standard page sizes
    letter = (8.5 * 72, 11 * 72)
    A4 = (8.27 * 72, 11.69 * 72)
    inch = 72

    class _RLDocStub:
        """
        Stub for reportlab.platypus.SimpleDocTemplate.

        Simulates PDF document creation without actually generating files.
        Stores the story elements for inspection and testing.
        """

        def __init__(self, filename, *args, **kwargs):
            """
            Initialize the document stub.

            Args:
                filename (str): Output filename for the PDF
                *args: Additional positional arguments
                **kwargs: Keyword arguments (pagesize, margins, etc.)
            """
            self.filename = filename
            self.pagesize = kwargs.get('pagesize', letter)
            self.leftMargin = kwargs.get('leftMargin', 72)
            self.rightMargin = kwargs.get('rightMargin', 72)
            self.topMargin = kwargs.get('topMargin', 72)
            self.bottomMargin = kwargs.get('bottomMargin', 72)
            self.title = kwargs.get('title', '')
            self.author = kwargs.get('author', '')
            self.story = []
            self._built = False
            logging.debug(f"Created PDF document stub: {filename}")

        def build(self, story, onFirstPage=None, onLaterPages=None, canvasmaker=None):
            """
            Simulate building the PDF document.

            Args:
                story (list): List of flowable elements to add to the document
                onFirstPage: Callback for first page (not used in stub)
                onLaterPages: Callback for later pages (not used in stub)
                canvasmaker: Custom canvas maker (not used in stub)
            """
            self.story = story
            self._built = True
            logging.info(
                f"PDF document stub built: {self.filename} "
                f"({len(story)} elements, reportlab not installed)"
            )
            warnings.warn(
                f"PDF '{self.filename}' not actually created (reportlab not installed). "
                f"Story contains {len(story)} elements.",
                RuntimeWarning
            )

        def multiBuild(self, story, *args, **kwargs):
            """Simulate multi-pass document building."""
            return self.build(story)

    class _RLTableStub:
        """
        Stub for reportlab.platypus.Table.

        Stores table data and styling for inspection without rendering.
        """

        def __init__(self, data, colWidths=None, rowHeights=None, style=None, *args, **kwargs):
            """
            Initialize the table stub.

            Args:
                data (list): 2D list of table data
                colWidths (list): Column widths
                rowHeights (list): Row heights
                style: Table style object
                *args: Additional positional arguments
                **kwargs: Additional keyword arguments
            """
            self.data = data
            self.colWidths = colWidths
            self.rowHeights = rowHeights
            self._style = style
            self.hAlign = kwargs.get('hAlign', 'CENTER')
            self.vAlign = kwargs.get('vAlign', 'MIDDLE')
            self._kwargs = kwargs
            logging.debug(
                f"Created table stub with {len(data) if data else 0} rows, "
                f"{len(data[0]) if data and data[0] else 0} columns"
            )

        def setStyle(self, style):
            """
            Set the table style.

            Args:
                style: TableStyle object or stub
            """
            self._style = style
            logging.debug(f"Table style set: {type(style).__name__}")

        def getKeepWithNext(self):
            """Get keep-with-next property."""
            return False

        def setKeepWithNext(self, val):
            """Set keep-with-next property."""
            pass

    class _RLTableStyleStub:
        """
        Stub for reportlab.platypus.TableStyle.

        Stores table styling commands without applying them.
        """

        def __init__(self, commands=None, parent=None, **kwargs):
            """
            Initialize the table style stub.

            Args:
                commands (list): List of style commands
                parent: Parent style (not used in stub)
                **kwargs: Additional style properties
            """
            self.commands = commands or []
            self.parent = parent
            self._kwargs = kwargs
            logging.debug(f"Created table style stub with {len(self.commands)} commands")

        def add(self, *commands):
            """Add style commands."""
            self.commands.extend(commands)

        def getCommands(self):
            """Get all style commands."""
            return self.commands

    class _RLParagraphStub:
        """
        Stub for reportlab.platypus.Paragraph.

        Stores paragraph text and style without rendering.
        """

        def __init__(self, text, style, *args, **kwargs):
            """
            Initialize the paragraph stub.

            Args:
                text (str): Paragraph text (may contain markup)
                style: ParagraphStyle object or stub
                *args: Additional positional arguments
                **kwargs: Additional keyword arguments
            """
            self.text = text
            self.style = style
            self._args = args
            self._kwargs = kwargs
            logging.debug(f"Created paragraph stub: {text[:50]}...")

        def getPlainText(self):
            """Get plain text without markup."""
            # Simple markup removal
            import re
            return re.sub(r'<[^>]+>', '', self.text)

        def wrap(self, availWidth, availHeight):
            """Simulate text wrapping."""
            return (availWidth, 100)  # Return dummy dimensions

        def split(self, availWidth, availHeight):
            """Simulate paragraph splitting."""
            return [self]

    class _RLSpacerStub:
        """
        Stub for reportlab.platypus.Spacer.

        Represents vertical space in a document.
        """

        def __init__(self, width, height, *args, **kwargs):
            """
            Initialize the spacer stub.

            Args:
                width: Spacer width
                height: Spacer height
                *args: Additional positional arguments
                **kwargs: Additional keyword arguments
            """
            self.width = width
            self.height = height
            self._args = args
            self._kwargs = kwargs
            logging.debug(f"Created spacer stub: {width}x{height}")

        def wrap(self, availWidth, availHeight):
            """Return spacer dimensions."""
            return (self.width, self.height)

    class _RLImageStub:
        """
        Stub for reportlab.platypus.Image.

        Represents an image without actually loading or rendering it.
        """

        def __init__(self, filename, width=None, height=None, *args, **kwargs):
            """
            Initialize the image stub.

            Args:
                filename (str): Path to image file
                width: Image width
                height: Image height
                *args: Additional positional arguments
                **kwargs: Additional keyword arguments
            """
            self.filename = filename
            self.width = width
            self.height = height
            self.hAlign = kwargs.get('hAlign', 'CENTER')
            self._args = args
            self._kwargs = kwargs
            logging.debug(f"Created image stub: {filename} ({width}x{height})")

        def wrap(self, availWidth, availHeight):
            """Return image dimensions."""
            w = self.width if self.width else availWidth
            h = self.height if self.height else 100
            return (w, h)

    class _RLPageBreakStub:
        """
        Stub for reportlab.platypus.PageBreak.

        Represents a page break in a document.
        """

        def __init__(self, *args, **kwargs):
            """Initialize the page break stub."""
            self._args = args
            self._kwargs = kwargs
            logging.debug("Created page break stub")

        def wrap(self, availWidth, availHeight):
            """Return zero dimensions."""
            return (0, 0)

    class _ColorsStub:
        """
        Stub for reportlab.lib.colors module.

        Provides common color constants without actual color objects.
        """

        def __init__(self):
            """Initialize common color constants."""
            # Define common colors as tuples (R, G, B, A)
            self.black = (0, 0, 0, 1)
            self.white = (1, 1, 1, 1)
            self.red = (1, 0, 0, 1)
            self.green = (0, 1, 0, 1)
            self.blue = (0, 0, 1, 1)
            self.yellow = (1, 1, 0, 1)
            self.cyan = (0, 1, 1, 1)
            self.magenta = (1, 0, 1, 1)
            self.grey = (0.5, 0.5, 0.5, 1)
            self.lightgrey = (0.75, 0.75, 0.75, 1)
            self.darkgrey = (0.25, 0.25, 0.25, 1)

        def HexColor(self, hexcode, *args, **kwargs):
            """Create color from hex code."""
            return hexcode

        def Color(self, r, g, b, a=1):
            """Create color from RGBA values."""
            return (r, g, b, a)

    def getSampleStyleSheet():
        """
        Return a sample stylesheet stub.

        Returns:
            dict: Dictionary with common style names
        """
        return {
            'Normal': ParagraphStyle('Normal'),
            'Heading1': ParagraphStyle('Heading1'),
            'Heading2': ParagraphStyle('Heading2'),
            'Heading3': ParagraphStyle('Heading3'),
            'Title': ParagraphStyle('Title'),
            'BodyText': ParagraphStyle('BodyText'),
            'Code': ParagraphStyle('Code'),
        }

    class ParagraphStyle:
        """
        Stub for reportlab.lib.styles.ParagraphStyle.

        Stores paragraph styling properties.
        """

        def __init__(self, name, parent=None, **kwargs):
            """
            Initialize the paragraph style stub.

            Args:
                name (str): Style name
                parent: Parent style (not used in stub)
                **kwargs: Style properties (fontSize, fontName, textColor, etc.)
            """
            self.name = name
            self.parent = parent
            self.fontName = kwargs.get('fontName', 'Helvetica')
            self.fontSize = kwargs.get('fontSize', 12)
            self.leading = kwargs.get('leading', 14)
            self.textColor = kwargs.get('textColor', (0, 0, 0, 1))
            self.alignment = kwargs.get('alignment', 0)  # 0=left, 1=center, 2=right
            self.spaceAfter = kwargs.get('spaceAfter', 0)
            self.spaceBefore = kwargs.get('spaceBefore', 0)
            self.leftIndent = kwargs.get('leftIndent', 0)
            self.rightIndent = kwargs.get('rightIndent', 0)
            self.firstLineIndent = kwargs.get('firstLineIndent', 0)
            self.bulletFontName = kwargs.get('bulletFontName', 'Helvetica')
            self.bulletFontSize = kwargs.get('bulletFontSize', 12)
            self._kwargs = kwargs
            logging.debug(f"Created paragraph style stub: {name}")

        def __repr__(self):
            return f"ParagraphStyle('{self.name}')"

    # Assign stubs to expected names
    colors = _ColorsStub()
    SimpleDocTemplate = _RLDocStub  # type: ignore
    Table = _RLTableStub  # type: ignore
    TableStyle = _RLTableStyleStub  # type: ignore
    Paragraph = _RLParagraphStub  # type: ignore
    Spacer = _RLSpacerStub  # type: ignore
    Image = _RLImageStub  # type: ignore
    PageBreak = _RLPageBreakStub  # type: ignore

# ── Flask ───────────────────────────────────────────────────────────────────
try:
    from flask import Flask, request, jsonify, session, render_template_string  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    warnings.warn(
        "Flask library not installed. Web server functionality will not work. "
        "Install with: pip install flask",
        RuntimeWarning
    )

    class _FlaskStub:
        """
        Stub for Flask application when Flask is not installed.

        Simulates Flask app behavior without actually starting a web server.
        Routes and handlers are registered but not served.
        """

        def __init__(self, import_name, *args, **kwargs):
            """
            Initialize the Flask stub.

            Args:
                import_name (str): Name of the application module
                *args: Additional positional arguments
                **kwargs: Configuration options
            """
            self.import_name = import_name
            self.config = kwargs.get('instance_path', {})
            self.debug = False
            self.testing = False
            self._routes = {}
            self._error_handlers = {}
            self._before_request_funcs = []
            self._after_request_funcs = []
            self._template_folder = kwargs.get('template_folder', 'templates')
            self._static_folder = kwargs.get('static_folder', 'static')
            self._secret_key = None
            logging.debug(f"Created Flask app stub: {import_name}")
            logging.warning("Flask not installed - web server will not start")

        def route(self, rule, **options):
            """
            Decorator to register a route handler.

            Args:
                rule (str): URL rule (e.g., '/api/data')
                **options: Additional route options (methods, defaults, etc.)

            Returns:
                function: Decorator function
            """
            def decorator(func):
                methods = options.get('methods', ['GET'])
                self._routes[rule] = {
                    'function': func,
                    'methods': methods,
                    'options': options
                }
                logging.debug(
                    f"Registered route stub: {methods} {rule} -> {func.__name__}"
                )
                return func
            return decorator

        def run(self, host=None, port=None, debug=None, **options):
            """
            Simulate running the Flask development server.

            Args:
                host (str): Server hostname (default: 127.0.0.1)
                port (int): Server port (default: 5000)
                debug (bool): Enable debug mode
                **options: Additional server options
            """
            host = host or '127.0.0.1'
            port = port or 5000
            if debug is not None:
                self.debug = debug

            logging.warning(
                f"Flask app '{self.import_name}' run() called but Flask not installed. "
                f"Would start server at http://{host}:{port}/"
            )
            logging.info(
                f"Registered routes in stub: {list(self._routes.keys())}"
            )
            warnings.warn(
                f"Flask web server not started (Flask not installed). "
                f"Would run at http://{host}:{port}/ with {len(self._routes)} routes.",
                RuntimeWarning
            )

        def errorhandler(self, code_or_exception):
            """
            Decorator to register an error handler.

            Args:
                code_or_exception: HTTP status code or exception class

            Returns:
                function: Decorator function
            """
            def decorator(func):
                self._error_handlers[code_or_exception] = func
                logging.debug(
                    f"Registered error handler stub: {code_or_exception} -> {func.__name__}"
                )
                return func
            return decorator

        def before_request(self, func):
            """
            Register a function to run before each request.

            Args:
                func: Function to execute before requests

            Returns:
                function: The same function
            """
            self._before_request_funcs.append(func)
            logging.debug(f"Registered before_request stub: {func.__name__}")
            return func

        def after_request(self, func):
            """
            Register a function to run after each request.

            Args:
                func: Function to execute after requests

            Returns:
                function: The same function
            """
            self._after_request_funcs.append(func)
            logging.debug(f"Registered after_request stub: {func.__name__}")
            return func

        def context_processor(self, func):
            """Register a template context processor."""
            logging.debug(f"Registered context_processor stub: {func.__name__}")
            return func

        def teardown_appcontext(self, func):
            """Register a function to call when app context tears down."""
            logging.debug(f"Registered teardown_appcontext stub: {func.__name__}")
            return func

        def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
            """Add a URL rule to the application."""
            self._routes[rule] = {
                'function': view_func,
                'endpoint': endpoint,
                'options': options
            }
            logging.debug(f"Added URL rule stub: {rule} -> {endpoint}")

        @property
        def secret_key(self):
            """Get the secret key."""
            return self._secret_key

        @secret_key.setter
        def secret_key(self, value):
            """Set the secret key."""
            self._secret_key = value

        def test_client(self):
            """Return a test client stub."""
            logging.warning("test_client() called but Flask not installed")
            return _FlaskTestClientStub()

    class _FlaskTestClientStub:
        """Stub for Flask test client."""

        def __init__(self):
            """Initialize test client stub."""
            logging.debug("Created Flask test client stub")

        def get(self, *args, **kwargs):
            """Simulate GET request."""
            logging.debug(f"Test client GET stub called: {args}")
            return _FlaskResponseStub()

        def post(self, *args, **kwargs):
            """Simulate POST request."""
            logging.debug(f"Test client POST stub called: {args}")
            return _FlaskResponseStub()

        def put(self, *args, **kwargs):
            """Simulate PUT request."""
            logging.debug(f"Test client PUT stub called: {args}")
            return _FlaskResponseStub()

        def delete(self, *args, **kwargs):
            """Simulate DELETE request."""
            logging.debug(f"Test client DELETE stub called: {args}")
            return _FlaskResponseStub()

    class _FlaskResponseStub:
        """Stub for Flask response object."""

        def __init__(self):
            """Initialize response stub."""
            self.status_code = 200
            self.data = b''
            self.headers = {}

        def get_json(self):
            """Get JSON data from response."""
            return {}

    class _RequestStub:
        """
        Stub for Flask request object.

        Provides empty/None values for all request attributes.
        """

        def __init__(self):
            """Initialize request stub with empty values."""
            self.method = 'GET'
            self.args = {}
            self.form = {}
            self.json = {}
            self.data = b''
            self.files = {}
            self.headers = {}
            self.cookies = {}
            self.path = '/'
            self.url = 'http://localhost:5000/'
            self.base_url = 'http://localhost:5000/'
            self.url_root = 'http://localhost:5000/'
            self.is_json = False
            self.is_secure = False
            self.remote_addr = '127.0.0.1'
            self.environ = {}
            logging.debug("Created Flask request stub")

        def __getattr__(self, name):
            """Return None for any unknown attributes."""
            logging.debug(f"Request stub attribute accessed: {name}")
            return None

        def get_json(self, *args, **kwargs):
            """Get JSON data from request."""
            return self.json

    class _SessionStub(dict):
        """
        Stub for Flask session object.

        Behaves like a dict but logs warnings about Flask not being installed.
        """

        def __init__(self):
            """Initialize session stub."""
            super().__init__()
            logging.debug("Created Flask session stub")

        def __setitem__(self, key, value):
            """Set session item with logging."""
            logging.debug(f"Session stub set: {key} = {value}")
            super().__setitem__(key, value)

        def __getitem__(self, key):
            """Get session item with logging."""
            logging.debug(f"Session stub get: {key}")
            return super().__getitem__(key)

    def jsonify(*args, **kwargs):
        """
        Stub for Flask jsonify function.

        Args:
            *args: Positional arguments (dicts to serialize)
            **kwargs: Keyword arguments (key-value pairs to serialize)

        Returns:
            dict: The input data as-is (not actually JSONified)
        """
        if args:
            data = args[0] if len(args) == 1 else args
        else:
            data = kwargs

        logging.debug(f"jsonify stub called with: {type(data).__name__}")
        return data

    def render_template_string(source, **context):
        """
        Stub for Flask render_template_string function.

        Args:
            source (str): Template source string
            **context: Template context variables

        Returns:
            str: The source string as-is (not actually rendered)
        """
        logging.debug(
            f"render_template_string stub called "
            f"(template length: {len(source)}, context: {list(context.keys())})"
        )
        # Simple variable substitution for basic testing
        result = source
        for key, value in context.items():
            result = result.replace(f'{{{{{key}}}}}', str(value))
        return result

    # Assign stubs to expected names
    Flask = _FlaskStub  # type: ignore
    request = _RequestStub()  # type: ignore
    session = _SessionStub()  # type: ignore

# ── sklearn ─────────────────────────────────────────────────────────────────
try:
    from sklearn.ensemble import RandomForestClassifier, IsolationForest  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
    from sklearn.preprocessing import StandardScaler  # type: ignore
    from sklearn.metrics import accuracy_score, classification_report  # type: ignore
except Exception as e:
    print(f"Optional dependency not installed: {e}")
    # Provide minimal sklearn stubs
    class _SKLearnDummy:
        def __init__(self, *args, **kwargs):
            pass
        def fit(self, *args, **kwargs):
            return self
        def predict(self, *args, **kwargs):
            return []
        def score(self, *args, **kwargs):
            return 0.0
        def transform(self, *args, **kwargs):
            return []
        def fit_transform(self, *args, **kwargs):
            return []
    RandomForestClassifier = _SKLearnDummy  # type: ignore
    IsolationForest = _SKLearnDummy  # type: ignore
    def train_test_split(*args, **kwargs):  # type: ignore
        return ([], [], [], [])
    StandardScaler = _SKLearnDummy  # type: ignore
    def accuracy_score(*args, **kwargs):  # type: ignore
        return 0.0
    def classification_report(*args, **kwargs):  # type: ignore
        return ""

# ── internal logging config ─────────────────────────────────────────────────
try:
    from education_system.university_system.utils.logging.config import configure_logging
    from education_system.university_system.utils.logging.config import get_log_file
except ImportError:
    # Fallback stubs if logging config not available
    def configure_logging(name=None):
        import logging
        return logging.getLogger(name or __name__)
    def get_log_file(filename="system.log"):
        from education_system.university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / filename)
