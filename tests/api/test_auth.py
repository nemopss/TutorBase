import pytest
from fastapi.testclient import TestClient

from api.app import create_app

app = create_app()
client = TestClient(app)


def test_login_missing_payload():
    response = client.post("/api/v1/auth/login", json={"init_data": "invalid"})
    assert response.status_code in {400, 401}


def test_refresh_invalid_token():
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid"})
    assert response.status_code == 401

