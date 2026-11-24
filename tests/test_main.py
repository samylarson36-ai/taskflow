
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    # Le contexte déclenche l'initialisation de l'application
    with TestClient(app) as test_client:
        yield test_client


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200


def test_get_tasks(client):
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "taskflow_tasks_created_total" in response.text
