import pytest

from accounts.models import User
from policies.services import accept_upload, claim_next, process_policy

from .test_upload_api import api_client, pdf

pytestmark = pytest.mark.django_db

URL = "/api/v1/policy/file"


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com", name="管理者", password="valid-password-2026", is_admin=True
    )


@pytest.fixture
def normal_user():
    return User.objects.create_user(
        email="normal@example.com", name="一般", password="valid-password-2026"
    )


def register(samples, user, name="dummy_policy.pdf"):
    accept_upload(pdf(samples, name), user)
    process_policy(claim_next())


def test_requires_login():
    assert api_client().get(URL).status_code == 401


@pytest.mark.parametrize("who", ["normal_user", "admin_user"])
def test_any_logged_in_user_gets_the_pdf(who, request, samples, admin_user):
    register(samples, admin_user)
    user = request.getfixturevalue(who)

    response = api_client(user).get(URL)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("inline")
    assert b"".join(response.streaming_content) == (samples / "dummy_policy.pdf").read_bytes()


def test_returns_404_when_nothing_is_registered(normal_user):
    response = api_client(normal_user).get(URL)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "POLICY_NOT_FOUND"


def test_does_not_return_a_pdf_that_is_still_processing(samples, admin_user, normal_user):
    accept_upload(pdf(samples), admin_user)

    assert api_client(normal_user).get(URL).status_code == 404


def test_returns_the_new_policy_after_replacement(samples, admin_user, normal_user):
    register(samples, admin_user)
    register(samples, admin_user, "dummy_policy_revised.pdf")

    response = api_client(normal_user).get(URL)

    assert (
        b"".join(response.streaming_content) == (samples / "dummy_policy_revised.pdf").read_bytes()
    )
