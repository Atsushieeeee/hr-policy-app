import pytest

from accounts.models import User
from policies.services import accept_upload

from .test_upload_api import api_client, pdf

pytestmark = pytest.mark.django_db

URL = "/api/v1/policy/status"


@pytest.fixture
def normal_user():
    return User.objects.create_user(
        email="normal@example.com", name="一般", password="valid-password-2026"
    )


def test_requires_login():
    assert api_client().get(URL).status_code == 401


def test_not_registered(normal_user):
    response = api_client(normal_user).get(URL)

    assert response.status_code == 200
    assert response.json() == {"registered": False}


def test_registered_for_any_logged_in_user(normal_user, registered_policy):
    response = api_client(normal_user).get(URL)

    assert response.status_code == 200
    assert response.json() == {"registered": True}


def test_processing_upload_is_not_registered(samples, normal_user):
    accept_upload(pdf(samples), normal_user)

    assert api_client(normal_user).get(URL).json() == {"registered": False}
