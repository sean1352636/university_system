from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import Flask

from education_system.platform.delivery.api.web.routes import web_bp as main_web_bp
from education_system.systems.university.interfaces.api.routes.web_routes import web_bp

STATIC = (
    Path(__file__).resolve().parents[5]
    / "education_system/platform/delivery/api/university/static"
)
PORTAL = (
    Path(__file__).resolve().parents[5]
    / "education_system/platform/delivery/api/web/portal"
)
PAGES = ("cases", "identity", "connectors", "timetabling", "pgr", "programmes")


class OperationsPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.landmarks = set()
        self.skip_link = False
        self.current = False
        self.labels = set()
        self.controls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if tag in {"header", "nav", "main"}:
            self.landmarks.add(tag)
        if tag == "a" and values.get("href") == "#main":
            self.skip_link = True
        if values.get("aria-current") == "page":
            self.current = True
        if tag == "label" and values.get("for"):
            self.labels.add(values["for"])
        if tag in {"input", "select", "textarea", "button"}:
            self.controls.append((tag, values))


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(web_bp)
    return app.test_client()


def test_operations_hub_links_every_workspace(client):
    response = client.get("/portal/operations")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert all(f'/portal/operations/{page}' in html for page in PAGES)
    assert "/portal/dashboard.html?system=university" in html


def test_main_portal_links_to_university_operations():
    dashboard = (PORTAL / "dashboard.html").read_text(encoding="utf-8")
    script = (PORTAL / "assets/portal.js").read_text(encoding="utf-8")
    assert 'href="/portal/operations"' in dashboard
    assert 'href="/portal/operations"' in script
    assert 'currentSystem !== "university"' in dashboard


def test_server_root_redirects_to_welcome_portal():
    app = Flask(__name__)
    app.register_blueprint(main_web_bp)
    response = app.test_client().get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/"


def test_login_inline_handler_has_a_matching_csp_nonce():
    app = Flask(__name__)
    app.register_blueprint(main_web_bp)
    response = app.test_client().get("/portal/login.html")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    csp = response.headers["Content-Security-Policy"]
    nonce = html.split('<script nonce="', 1)[1].split('"', 1)[0]
    assert f"'nonce-{nonce}'" in csp
    assert '<form id="login-form" method="post"' in html


def test_welcome_and_login_pages_link_to_each_other():
    welcome = (PORTAL / "index.html").read_text(encoding="utf-8")
    login = (PORTAL / "login.html").read_text(encoding="utf-8")
    assert '<a class="btn" href="/web/login">Login</a>' in welcome
    assert welcome.count('href="/web/login"') == 1
    assert 'href="/portal/login.html">Login</a>' not in welcome
    assert 'id="systems-grid"' not in welcome
    assert "EduPortal.SYSTEMS.map" not in welcome
    assert 'href="/portal/operations/pgr">Postgraduate research</a>' in welcome
    assert 'cta.insertAdjacentHTML("beforeend"' in welcome
    assert 'href="/portal/"' in login
    assert "Return to welcome page" in login
    assert "If already signed in, jump to dashboard" not in login
    assert "<code>admin</code> / <code>admin123</code>" in login
    assert "superadmin account requires an MFA code" in login


def test_api_login_screen_links_back_to_homepage():
    script = (
        PORTAL.parent / "static/js/app.js"
    ).read_text(encoding="utf-8")
    assert 'href="/portal/"' in script
    assert "Return to homepage" in script


def test_static_university_startup_uses_public_welcome_page():
    web_dir = (
        Path(__file__).resolve().parents[5]
        / "education_system/systems/university/assets/web"
    )
    welcome = (web_dir / "university.html").read_text(encoding="utf-8")
    login = (web_dir / "login.html").read_text(encoding="utf-8")
    launcher = (
        Path(__file__).resolve().parents[5] / "run.py"
    ).read_text(encoding="utf-8")
    assert 'url = f"http://localhost:{port}/university.html"' in launcher
    assert 'id="login-btn" href="login.html"' in welcome
    assert "login-btn').style.display = 'none'" not in welcome
    assert "if (!session) return;" in welcome
    assert 'href="university.html"' in login
    assert "Return to welcome page" in login
    assert "Already logged in? Bounce" not in login


@pytest.mark.parametrize("page", PAGES)
def test_operations_page_is_accessible_and_served(client, page):
    response = client.get(f"/portal/operations/{page}")
    assert response.status_code == 200
    parser = OperationsPageParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.lang == "en"
    assert parser.landmarks == {"header", "nav", "main"}
    assert parser.skip_link
    assert parser.current
    assert all(
        tag == "button"
        or attrs.get("aria-label")
        or attrs.get("id") in parser.labels
        or (tag == "input" and attrs.get("type") in {"checkbox", "radio"})
        for tag, attrs in parser.controls
    )


def test_unknown_operations_workspace_is_not_exposed(client):
    assert client.get("/portal/operations/private").status_code == 404


@pytest.mark.parametrize(
    ("asset", "content_type"),
    (
        ("css/journey.css", "text/css"),
        ("js/student_pages.js", "text/javascript"),
        ("js/institutional_pages.js", "text/javascript"),
    ),
)
def test_operations_assets_are_served_from_the_same_blueprint(
    client, asset, content_type
):
    response = client.get(f"/portal/operations/assets/{asset}")
    assert response.status_code == 200
    assert response.content_type.startswith(content_type)


def test_every_operations_page_uses_shared_script_and_styles():
    for page in PAGES:
        html = (STATIC / f"operations-{page}.html").read_text(encoding="utf-8")
        assert "/portal/operations/assets/css/journey.css" in html
        assert "/portal/operations/assets/js/institutional_pages.js" in html


def test_operations_script_provides_a_complete_sign_out():
    script = (
        STATIC / "js/institutional_pages.js"
    ).read_text(encoding="utf-8")
    for key in (
        "edu_portal_token",
        "edu_portal_refresh",
        "edu_portal_user",
        "edu_portal_active_system",
    ):
        assert f'localStorage.removeItem("{key}")' in script
    assert 'button.textContent = "Sign out"' in script
    assert 'location.href = "/portal/"' in script
