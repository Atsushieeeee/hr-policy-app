from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from pypdf import PdfWriter

from accounts.models import User
from policies.models import PolicyDocument
from policies.services import (
    accept_upload,
    claim_next,
    current_policy,
    expire_stale_processing,
    process_policy,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com", name="管理者", password="valid-password-2026", is_admin=True
    )


def upload(admin_user, samples, name="dummy_policy.pdf"):
    data = (samples / name).read_bytes()
    return accept_upload(SimpleUploadedFile(name.split("/")[-1], data), admin_user)


def upload_bytes(admin_user, data, name="x.pdf"):
    return accept_upload(SimpleUploadedFile(name, data), admin_user)


def run_worker_once():
    policy = claim_next()
    process_policy(policy)
    policy.refresh_from_db()
    return policy


class TestProcessing:
    def test_extracts_text_with_page_markers(self, admin_user, samples):
        upload(admin_user, samples)

        policy = run_worker_once()

        assert policy.status == PolicyDocument.Status.READY
        assert policy.page_count == 3
        assert policy.extracted_text.startswith("[p.1]")
        assert [f"[p.{n}]" in policy.extracted_text for n in (1, 2, 3)] == [True] * 3
        assert "[p.4]" not in policy.extracted_text

    def test_becomes_the_current_policy(self, admin_user, samples):
        upload(admin_user, samples)

        policy = run_worker_once()

        assert current_policy() == policy

    def test_replacing_deletes_the_old_policy_and_its_file(self, admin_user, samples):
        old = run_worker_once_after(admin_user, samples, "dummy_policy.pdf")
        old_name = old.file.name

        new = run_worker_once_after(admin_user, samples, "dummy_policy_revised.pdf")

        assert PolicyDocument.objects.count() == 1
        assert current_policy() == new
        assert not new.file.storage.exists(old_name)
        assert new.file.storage.exists(new.file.name)

    def test_failure_keeps_the_old_policy(self, admin_user, samples):
        old = run_worker_once_after(admin_user, samples, "dummy_policy.pdf")
        upload(admin_user, samples, "invalid/no_text.pdf")

        failed = run_worker_once()

        assert failed.status == PolicyDocument.Status.FAILED
        assert failed.error_code == "PDF_NO_TEXT"
        assert failed.error_message
        assert current_policy() == old
        assert old.file.storage.exists(old.file.name)

    def test_worker_command_processes_the_queue(self, admin_user, samples):
        upload(admin_user, samples)

        call_command("run_policy_worker", once=True)

        assert current_policy() is not None


class TestFailures:
    def test_broken_pdf(self, admin_user):
        upload_bytes(admin_user, b"%PDF-1.4 this is not a real pdf")

        policy = run_worker_once()

        assert policy.status == PolicyDocument.Status.FAILED
        assert policy.error_code == "INVALID_FILE"

    def test_password_protected_pdf(self, admin_user, samples):
        from pypdf import PdfReader

        writer = PdfWriter()
        for page in PdfReader(str(samples / "dummy_policy.pdf")).pages:
            writer.add_page(page)
        writer.encrypt("secret", algorithm="AES-256")
        buffer = BytesIO()
        writer.write(buffer)
        upload_bytes(admin_user, buffer.getvalue())

        policy = run_worker_once()

        assert policy.error_code == "INVALID_FILE"
        assert "パスワード" in policy.error_message

    def test_too_many_pages(self, admin_user, samples, settings):
        settings.POLICY_MAX_PAGES = 2
        upload(admin_user, samples)

        assert run_worker_once().error_code == "TOO_MANY_PAGES"

    def test_text_too_long(self, admin_user, samples, settings):
        settings.POLICY_MAX_TEXT_CHARS = 100
        upload(admin_user, samples)

        policy = run_worker_once()

        assert policy.error_code == "POLICY_TOO_LONG"
        assert "上限" in policy.error_message

    def test_garbled_text(self, admin_user, samples, monkeypatch):
        monkeypatch.setattr("policies.services.garbled_ratio", lambda text: 1.0)
        upload(admin_user, samples)

        assert run_worker_once().error_code == "PDF_TEXT_GARBLED"

    def test_unexpected_error_is_recorded_as_failure(self, admin_user, samples, monkeypatch):
        def boom(data):
            raise RuntimeError("想定外のエラー")

        monkeypatch.setattr("policies.services.extract_policy_text", boom)
        upload(admin_user, samples)

        policy = run_worker_once()

        assert policy.status == PolicyDocument.Status.FAILED
        assert policy.error_code == "PROCESSING_ERROR"


class TestQueue:
    def test_claims_the_oldest_first_and_only_once(self, admin_user, samples):
        first = upload(admin_user, samples)

        claimed = claim_next()

        assert claimed == first
        assert claimed.started_at is not None
        assert claim_next() is None  # すでに処理を始めたものは、取り出さない

    def test_returns_none_when_there_is_nothing_to_do(self):
        assert claim_next() is None

    def test_interrupted_processing_is_marked_as_failed(self, admin_user, samples):
        policy = upload(admin_user, samples)
        claim_next()
        PolicyDocument.objects.filter(id=policy.id).update(
            started_at=timezone.now() - timedelta(minutes=11)
        )

        expire_stale_processing()

        policy.refresh_from_db()
        assert policy.status == PolicyDocument.Status.FAILED
        assert policy.error_code == "PROCESSING_INTERRUPTED"

    def test_recent_processing_is_left_alone(self, admin_user, samples):
        policy = upload(admin_user, samples)
        claim_next()

        expire_stale_processing()

        policy.refresh_from_db()
        assert policy.status == PolicyDocument.Status.PROCESSING


def run_worker_once_after(admin_user, samples, name):
    upload(admin_user, samples, name)
    return run_worker_once()
