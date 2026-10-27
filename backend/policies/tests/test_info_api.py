from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from policies.models import PolicyDocument
from policies.services import accept_upload, claim_next, process_policy

from .test_upload_api import api_client, pdf

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/policy"
FILE_URL = "/api/v1/admin/policy/file"


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
    return PolicyDocument.objects.get(status=PolicyDocument.Status.READY)


class TestAccess:
    @pytest.mark.parametrize("url", [URL, FILE_URL])
    def test_requires_login(self, url):
        assert api_client().get(url).status_code == 401

    @pytest.mark.parametrize("url", [URL, FILE_URL])
    def test_requires_admin_permission(self, url, normal_user):
        assert api_client(normal_user).get(url).status_code == 403


class TestInfo:
    def test_returns_200_with_nulls_when_nothing_is_registered(self, admin_user):
        response = api_client(admin_user).get(URL)

        assert response.status_code == 200
        assert response.json() == {"current": None, "upload": None}

    def test_returns_current_policy(self, samples, admin_user):
        policy = register(samples, admin_user)

        current = api_client(admin_user).get(URL).json()["current"]

        assert current["original_filename"] == "dummy_policy.pdf"
        assert current["uploaded_by"] == {"id": admin_user.id, "name": "管理者"}
        assert current["page_count"] == policy.page_count
        assert current["file_size"] == policy.file_size
        assert current["uploaded_at"]

    def test_returns_processing_upload(self, samples, admin_user):
        accept_upload(pdf(samples), admin_user)

        body = api_client(admin_user).get(URL).json()

        assert body["current"] is None
        assert body["upload"]["status"] == "processing"
        assert body["upload"]["original_filename"] == "dummy_policy.pdf"

    def test_returns_failed_upload_with_reason(self, samples, admin_user):
        accept_upload(pdf(samples, "invalid/no_text.pdf"), admin_user)
        process_policy(claim_next())

        upload = api_client(admin_user).get(URL).json()["upload"]

        assert upload["status"] == "failed"
        assert upload["error_code"]
        assert upload["error_message"]

    def test_returns_current_and_new_upload_together(self, samples, admin_user):
        register(samples, admin_user)
        accept_upload(pdf(samples, "dummy_policy_revised.pdf"), admin_user)

        body = api_client(admin_user).get(URL).json()

        assert body["current"]["original_filename"] == "dummy_policy.pdf"
        assert body["upload"]["status"] == "processing"

    def test_stuck_processing_is_reported_as_failed(self, samples, admin_user):
        stuck = accept_upload(pdf(samples), admin_user)
        PolicyDocument.objects.filter(id=stuck.id).update(
            started_at=timezone.now() - timedelta(minutes=11)
        )

        upload = api_client(admin_user).get(URL).json()["upload"]

        assert upload["status"] == "failed"
        assert upload["error_code"] == "PROCESSING_INTERRUPTED"


class TestFile:
    def test_returns_pdf_displayable_in_browser(self, samples, admin_user):
        register(samples, admin_user)

        response = api_client(admin_user).get(FILE_URL)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("inline")
        assert b"".join(response.streaming_content) == (samples / "dummy_policy.pdf").read_bytes()

    def test_returns_404_when_nothing_is_registered(self, admin_user):
        response = api_client(admin_user).get(FILE_URL)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "POLICY_NOT_FOUND"

    def test_does_not_return_a_pdf_that_is_still_processing(self, samples, admin_user):
        accept_upload(pdf(samples), admin_user)

        assert api_client(admin_user).get(FILE_URL).status_code == 404
