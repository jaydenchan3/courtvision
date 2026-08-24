"""Integration layer: auth through Flask's test client, no browser.

Status codes, session contents and redirect targets are all provable here.
The E2E layer covers only what needs a rendered page.
"""

import pytest

from app.server import MSG_BAD_LOGIN, safe_next

pytestmark = [pytest.mark.integration, pytest.mark.auth]

PROTECTED = ["/", "/api/dashboard", "/roster", "/waiver", "/search"]
PROTECTED_POSTS = ["/roster/add", "/roster/remove"]


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_get_routes_redirect_when_anonymous(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


@pytest.mark.parametrize("path", PROTECTED_POSTS)
def test_protected_post_routes_redirect_when_anonymous(client, path):
    response = client.post(path, data={"player_id": 1})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_redirect_preserves_the_intended_destination(client):
    assert client.get("/roster").headers["Location"] == "/login?next=/roster"


def test_bad_password_returns_401_and_creates_no_session(client):
    response = client.post("/login", data={"username": "demo", "password": "wrong"})

    assert response.status_code == 401
    assert MSG_BAD_LOGIN in response.get_data(as_text=True)
    with client.session_transaction() as session:
        assert "user" not in session


def test_unknown_user_gives_the_same_message(client):
    """Identical wording for a bad user and a bad password: a different message
    would let an attacker enumerate valid usernames."""
    response = client.post("/login", data={"username": "nobody", "password": "x"})
    assert response.status_code == 401
    assert MSG_BAD_LOGIN in response.get_data(as_text=True)


def test_password_is_not_echoed_back_into_the_page(client):
    response = client.post("/login", data={"username": "demo", "password": "hunter2"})
    assert "hunter2" not in response.get_data(as_text=True)


def test_good_password_sets_the_session_and_redirects(client):
    response = client.post("/login", data={"username": "demo", "password": "courtvision"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with client.session_transaction() as session:
        assert session["user"] == "demo"


def test_logout_clears_the_session(client):
    client.post("/login", data={"username": "demo", "password": "courtvision"})
    response = client.post("/logout")

    assert response.headers["Location"] == "/login"
    with client.session_transaction() as session:
        assert "user" not in session
    assert client.get("/roster").status_code == 302


def test_same_site_next_is_honoured(client):
    response = client.post("/login?next=/waiver",
                           data={"username": "demo", "password": "courtvision"})
    assert response.headers["Location"] == "/waiver"


def test_offsite_next_is_discarded(client):
    """An off-site next value would turn our own login page into a phishing
    hop, so it is dropped and the user lands on the dashboard."""
    response = client.post("/login?next=https://evil.example/steal",
                           data={"username": "demo", "password": "courtvision"})
    assert response.headers["Location"] == "/"


@pytest.mark.parametrize("target,expected", [
    ("/roster", "/roster"),
    ("/waiver?sort=name", "/waiver?sort=name"),
    ("https://evil.example", None),
    ("//evil.example", None),          # protocol-relative: another host
    ("javascript:alert(1)", None),
    ("", None),
    (None, None),
])
def test_safe_next_only_permits_same_site_relative_paths(target, expected):
    assert safe_next(target) == expected
