"""Session-gated JSON API under /api/."""

import pytest


@pytest.mark.api
def test_api_accounts_unauthenticated_401_json(client):
    response = client.get("/api/accounts")
    assert response.status_code == 401
    body = response.get_json()
    assert body is not None
    assert "error" in body


@pytest.mark.api
def test_api_transactions_unauthenticated_401(client):
    response = client.get("/api/transactions")
    assert response.status_code == 401


@pytest.mark.api
def test_api_accounts_after_login_non_empty(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    response = client.get("/api/accounts")
    assert response.status_code == 200
    data = response.get_json()
    assert "accounts" in data
    assert isinstance(data["accounts"], list)
    assert len(data["accounts"]) >= 1


@pytest.mark.api
def test_api_transactions_after_login_list_shape(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    response = client.get("/api/transactions")
    assert response.status_code == 200
    data = response.get_json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)


@pytest.mark.api
def test_api_account_detail_unknown_404(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    response = client.get("/api/account/999999")
    assert response.status_code == 404


@pytest.mark.api
def test_api_account_detail_valid_id_200(client):
    client.post("/login", data={"username": "demo"}, follow_redirects=True)
    accounts = client.get("/api/accounts").get_json()["accounts"]
    account_id = accounts[0]["id"]
    response = client.get(f"/api/account/{account_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert "account" in body
    assert body["account"]["id"] == account_id
