"""Unauthenticated routes: status codes and small stable substrings (Split-safe)."""

import pytest


@pytest.mark.public
def test_home_root_200_contains_quantum(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"quantum" in response.data.lower()


@pytest.mark.public
def test_demo_entry_200_contains_quantum(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert b"quantum" in response.data.lower()


@pytest.mark.public
def test_pricing_200(client):
    response = client.get("/pricing")
    assert response.status_code == 200


@pytest.mark.public
def test_hello_200(client):
    response = client.get("/hello")
    assert response.status_code == 200
    assert b"Hello, World!" in response.data


@pytest.mark.public
def test_time_200_shows_time_label(client):
    response = client.get("/time")
    assert response.status_code == 200
    assert b"Current server time is:" in response.data


@pytest.mark.public
def test_about_200_plain_text(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert b"This is a simple HTTP server." in response.data


@pytest.mark.public
def test_home_content_json_shape(client):
    response = client.get("/api/home-content")
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert "treatment" in body
    assert "template" in body
    assert "url" in body


@pytest.mark.public
@pytest.mark.parametrize(
    "path",
    (
        "/old-home-static",
        "/new-home-static",
        "/v3-home-static",
        "/old-pricing-static",
        "/new-pricing-static",
        "/v3-pricing-static",
    ),
)
def test_static_variant_routes_200(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.public
def test_unknown_path_404(client):
    response = client.get("/yodawg20044")
    assert response.status_code == 404
    assert b"404" in response.data


@pytest.mark.public
def test_metrics_optional(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.get_data(as_text=True)
    assert "# HELP" in data or "# TYPE" in data
