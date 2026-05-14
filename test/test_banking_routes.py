"""Login, session, and authenticated HTML banking routes."""

import pytest


@pytest.mark.banking
def test_login_get_200(client):
    response = client.get("/login")
    assert response.status_code == 200


@pytest.mark.banking
def test_login_post_missing_username_shows_error(client):
    response = client.post("/login", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Username is required" in response.data


@pytest.mark.banking
def test_login_post_unknown_user(client):
    response = client.post(
        "/login", data={"username": "not_a_real_user_xyz"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"User not found" in response.data


@pytest.mark.banking
def test_login_post_demo_redirects_to_dashboard(client):
    response = client.post("/login", data={"username": "demo"}, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "dashboard" in response.headers.get("Location", "").lower()


@pytest.mark.banking
def test_login_post_demo_followed_renders_dashboard(client):
    response = client.post("/login", data={"username": "demo"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Your Accounts" in response.data


@pytest.mark.banking
def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "login" in response.headers.get("Location", "").lower()


@pytest.mark.banking
def test_logout_after_login_redirects_to_login(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "login" in response.headers.get("Location", "").lower()


@pytest.mark.banking
def test_transactions_authenticated_200(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    response = client.get("/transactions")
    assert response.status_code == 200
    assert b"All Transactions" in response.data


@pytest.mark.banking
def test_account_detail_authenticated_200(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    acct = client.get("/api/accounts").get_json()["accounts"][0]
    response = client.get(f"/account?id={acct['id']}")
    assert response.status_code == 200
    assert b"Back to Dashboard" in response.data
