from copy import deepcopy
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src import app as app_module


@pytest.fixture
def activities(monkeypatch):
    data = {
        "Chess Club": {
            "description": "Play chess",
            "schedule": "Fridays",
            "max_participants": 12,
            "participants": ["existing@mergington.edu"],
        }
    }
    monkeypatch.setattr(app_module, "activities", data)
    return data


@pytest.fixture
def client(activities):
    with TestClient(app_module.app) as test_client:
        yield test_client


def test_root_redirects_to_index(client):
    # Arrange
    expected_location = "/static/index.html"

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == expected_location


def test_get_activities_returns_current_data_without_caching(client, activities):
    # Arrange
    expected = deepcopy(activities)

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected


def test_signup_adds_participant(client, activities):
    # Arrange
    activity_name = "Chess Club"
    email = "new@mergington.edu"

    # Act
    response = client.post(
        f"/activities/{quote(activity_name, safe='')}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert activities[activity_name]["participants"] == [
        "existing@mergington.edu",
        email,
    ]
    assert client.get("/activities").json() == activities


def test_unregister_removes_participant(client, activities):
    # Arrange
    activity_name = "Chess Club"
    email = "existing@mergington.edu"

    # Act
    response = client.delete(
        f"/activities/{quote(activity_name, safe='')}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {activity_name}"}
    assert activities[activity_name]["participants"] == []
    assert client.get("/activities").json() == activities


@pytest.mark.parametrize(
    ("method", "activity_name", "email", "status_code", "detail"),
    [
        ("post", "Missing Club", "new@mergington.edu", 404, "Activity not found"),
        ("delete", "Missing Club", "new@mergington.edu", 404, "Activity not found"),
        (
            "post",
            "Chess Club",
            "existing@mergington.edu",
            400,
            "Student already signed up for this activity",
        ),
        (
            "delete",
            "Chess Club",
            "missing@mergington.edu",
            404,
            "Student not signed up for this activity",
        ),
    ],
)
def test_failed_signup_operations_leave_data_unchanged(
    client, activities, method, activity_name, email, status_code, detail
):
    # Arrange
    original = deepcopy(activities)

    # Act
    response = client.request(
        method,
        f"/activities/{quote(activity_name, safe='')}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert activities == original


@pytest.mark.parametrize("method", ["post", "delete"])
def test_signup_operations_require_email(client, activities, method):
    # Arrange
    original = deepcopy(activities)

    # Act
    response = client.request(method, "/activities/Chess%20Club/signup")

    # Assert
    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", "email"]
        for error in response.json()["detail"]
    )
    assert activities == original
