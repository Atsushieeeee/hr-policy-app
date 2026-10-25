from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_healthz_ok_when_db_is_available(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_api_v1_healthz_is_also_available(client):
    with patch("core.views.connection"):
        response = client.get("/api/v1/healthz")

    assert response.status_code == 200


def test_healthz_returns_503_when_db_is_down(client):
    with patch("core.views.connection") as connection:
        connection.cursor.side_effect = Exception("db down")
        response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
