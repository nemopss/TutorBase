import pytest
from fastapi.testclient import TestClient

from api.app import create_app

app = create_app()
client = TestClient(app)


def test_packages_requires_auth():
    response = client.get("/api/v1/packages")
    assert response.status_code == 401

