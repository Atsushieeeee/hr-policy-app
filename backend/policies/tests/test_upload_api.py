import threading
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from policies.exceptions import UploadInProgress
from policies.models import PolicyDocument
from policies.services import accept_upload, advisory_lock, claim_next, process_policy

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/policy"


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


def api_client(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)))
    return client


def pdf(samples, name="dummy_policy.pdf", filename=None):
    data = (samples / name).read_bytes()
    return SimpleUploadedFile(filename or name.split("/")[-1], data, content_type="application/pdf")


def put(client, file=None):
    data = {"file": file} if file is not None else {}
    return client.put(URL, data, format="multipart")


class TestAccess:
    def test_requires_login(self, samples):
        response = put(api_client(), pdf(samples))

        assert response.status_code == 401

    def test_requires_admin_permission(self, samples, normal_user):
        response = put(api_client(normal_user), pdf(samples))

        assert response.status_code == 403
        assert PolicyDocument.objects.count() == 0


class TestAccept:
    def test_accepts_pdf_and_queues_it_for_processing(self, samples, admin_user):
        response = put(api_client(admin_user), pdf(samples))

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "processing"
        assert body["original_filename"] == "dummy_policy.pdf"
        policy = PolicyDocument.objects.get(id=body["id"])
        assert policy.uploaded_by == admin_user
        assert policy.extracted_text == ""  # 取り込みは、ワーカーが行う

    def test_file_is_stored_with_a_random_name(self, samples, admin_user):
        put(api_client(admin_user), pdf(samples))

        policy = PolicyDocument.objects.get()
        assert policy.file.name.startswith("policies/")
        assert "dummy_policy" not in policy.file.name
        assert policy.file.name.endswith(".pdf")
        assert policy.file.storage.exists(policy.file.name)

    def test_pdf_is_detected_by_signature_not_extension(self, samples, admin_user):
        response = put(api_client(admin_user), pdf(samples, filename="policy.txt"))

        assert response.status_code == 202

    def test_requires_file(self, admin_user):
        response = put(api_client(admin_user))

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_file_that_is_not_pdf(self, samples, admin_user):
        response = put(api_client(admin_user), pdf(samples, "invalid/not_a_pdf.pdf"))

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_FILE"
        assert PolicyDocument.objects.count() == 0

    def test_rejects_too_large_file(self, samples, admin_user, settings):
        settings.POLICY_MAX_UPLOAD_MB = 0

        response = put(api_client(admin_user), pdf(samples))

        assert response.status_code == 413
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
        assert PolicyDocument.objects.count() == 0

    def test_rejects_same_file_as_current_policy(self, samples, admin_user):
        accept_upload(pdf(samples), admin_user)
        process_policy(claim_next())

        response = put(api_client(admin_user), pdf(samples))

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SAME_FILE"

    def test_accepts_different_file_while_a_policy_is_current(self, samples, admin_user):
        accept_upload(pdf(samples), admin_user)
        process_policy(claim_next())

        response = put(api_client(admin_user), pdf(samples, "dummy_policy_revised.pdf"))

        assert response.status_code == 202

    def test_rejects_upload_while_another_is_processing(self, samples, admin_user):
        accept_upload(pdf(samples), admin_user)

        response = put(api_client(admin_user), pdf(samples, "dummy_policy_revised.pdf"))

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "UPLOAD_IN_PROGRESS"
        assert PolicyDocument.objects.count() == 1

    def test_stale_processing_does_not_block_new_uploads(self, samples, admin_user):
        stuck = accept_upload(pdf(samples), admin_user)
        PolicyDocument.objects.filter(id=stuck.id).update(
            started_at=timezone.now() - timedelta(minutes=11)
        )

        response = put(api_client(admin_user), pdf(samples, "dummy_policy_revised.pdf"))

        assert response.status_code == 202
        assert not PolicyDocument.objects.filter(id=stuck.id).exists()  # 失敗の記録は、片付けられる

    def test_previous_failure_is_cleared_by_the_next_upload(self, samples, admin_user):
        accept_upload(pdf(samples, "invalid/no_text.pdf"), admin_user)
        process_policy(claim_next())
        failed = PolicyDocument.objects.get()
        assert failed.status == PolicyDocument.Status.FAILED
        name = failed.file.name

        put(api_client(admin_user), pdf(samples))

        assert not PolicyDocument.objects.filter(id=failed.id).exists()
        assert not failed.file.storage.exists(name)

    def test_upload_is_rate_limited(self, samples, admin_user, set_rate, clock):
        set_rate("policy_upload", "2/hour")
        client = api_client(admin_user)
        put(client, pdf(samples))
        put(client, pdf(samples))  # 処理中の409でも、回数には数える

        response = put(client, pdf(samples))

        assert response.status_code == 429
        assert int(response["Retry-After"]) > 0


@pytest.mark.django_db(transaction=True)
def test_only_one_upload_is_accepted_at_a_time(samples, admin_user):
    errors = []

    def upload_in_another_connection():
        try:
            accept_upload(pdf(samples), admin_user)
        except UploadInProgress as e:
            errors.append(e)
        finally:
            connection.close()

    # 別の接続が、取り込みの受け付けのロックを持っている間は、受け付けない
    with advisory_lock("policy_upload"):
        thread = threading.Thread(target=upload_in_another_connection)
        thread.start()
        thread.join()

    assert len(errors) == 1
    assert PolicyDocument.objects.count() == 0
