import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from audit.models import AppendOnlyError, AuditLog
from audit.services import record
from policies.services import accept_upload, claim_next, process_policy

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
LOGIN = "/api/v1/auth/login"
ADMINS = "/api/v1/admin/admins"
REVOKE = "/api/v1/admin/admins/revoke"
Action = AuditLog.Action


def make_user(name, is_admin=False):
    return User.objects.create_user(
        email=f"{name}@example.com", name=name, password=PASSWORD, is_admin=is_admin
    )


def api(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)))
    return client


def logs(action=None):
    queryset = AuditLog.objects.order_by("id")
    return list(queryset.filter(action=action) if action else queryset)


def dump(log):
    """記録の全項目を、1つの文字列にする（秘密が含まれていないかの確認用）。"""
    return json.dumps(
        [log.actor_email, log.target_type, log.target_id, log.detail, log.ip], ensure_ascii=False
    )


class TestAppendOnly:
    def test_a_saved_row_cannot_be_changed_or_deleted(self):
        record(Action.LOGIN_SUCCESS, actor_email="a@example.com")
        log = logs()[0]

        log.actor_email = "b@example.com"
        with pytest.raises(AppendOnlyError):
            log.save()
        with pytest.raises(AppendOnlyError):
            log.delete()

    def test_bulk_update_and_delete_are_refused(self):
        record(Action.LOGIN_SUCCESS, actor_email="a@example.com")

        with pytest.raises(AppendOnlyError):
            AuditLog.objects.update(actor_email="x")
        with pytest.raises(AppendOnlyError):
            AuditLog.objects.filter(action=Action.LOGIN_SUCCESS).delete()
        assert logs()[0].actor_email == "a@example.com"

    def test_the_log_survives_when_the_user_is_deleted(self):
        user = make_user("gone")
        record(Action.LOGIN_SUCCESS, actor=user)

        user.delete()

        log = logs()[0]
        assert log.actor is None and log.actor_email == "gone@example.com"


class TestRecord:
    def test_stores_the_fields_and_the_ip(self):
        user = make_user("a")
        request = APIRequestFactory().get("/", REMOTE_ADDR="203.0.113.7")

        record(
            Action.ADMIN_GRANT,
            actor=user,
            request=request,
            target_type="user",
            target_id=5,
            detail={"email": "b@example.com"},
        )

        log = logs()[0]
        assert (log.actor, log.actor_email) == (user, "a@example.com")
        assert (log.target_type, log.target_id) == ("user", "5")
        assert log.detail == {"email": "b@example.com"}
        assert log.ip == "203.0.113.7"

    def test_an_invalid_forwarded_address_is_not_stored(self, settings):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
        request = APIRequestFactory().get("/", HTTP_X_FORWARDED_FOR="not-an-ip")

        record(Action.LOGIN_SUCCESS, actor_email="a@example.com", request=request)

        assert logs()[0].ip is None

    def test_a_failure_to_record_does_not_break_the_caller_or_its_transaction(self):
        with transaction.atomic():
            make_user("kept")
            # 長すぎて、DBが拒否する
            record(Action.LOGIN_SUCCESS, actor_email="x" * 500)
            make_user("also-kept")

        assert (
            User.objects.filter(email__in=["kept@example.com", "also-kept@example.com"]).count()
            == 2
        )
        assert logs() == []


class TestLogin:
    def test_success_is_recorded_with_the_user_and_ip(self):
        user = make_user("a")

        response = APIClient().post(LOGIN, {"email": "a@example.com", "password": PASSWORD})

        assert response.status_code == 200
        log = logs(Action.LOGIN_SUCCESS)[0]
        assert log.actor == user and log.ip == "127.0.0.1"

    def test_failure_is_recorded_with_the_attempted_email_but_not_the_password(self):
        make_user("a")

        response = APIClient().post(LOGIN, {"email": "A@example.com", "password": "wrong-secret-9"})

        assert response.status_code == 401
        log = logs(Action.LOGIN_FAILURE)[0]
        assert log.actor is None
        assert log.actor_email == "a@example.com"
        assert log.detail == {"reason": "invalid_credentials"}
        assert "wrong-secret-9" not in dump(log)

    def test_unknown_email_is_recorded_too(self):
        APIClient().post(LOGIN, {"email": "nobody@example.com", "password": PASSWORD})

        assert logs(Action.LOGIN_FAILURE)[0].actor_email == "nobody@example.com"

    def test_something_that_is_not_an_email_is_not_recorded(self):
        # 利用者が、パスワードを、メールアドレスの欄に入力してしまった場合
        APIClient().post(LOGIN, {"email": "my-secret-password-1", "password": "x"})

        log = logs(Action.LOGIN_FAILURE)[0]
        assert log.actor_email == ""
        assert "my-secret-password-1" not in dump(log)

    def test_attempts_while_locked_are_recorded_with_the_reason(self, clock, settings):
        make_user("a")
        for _ in range(settings.LOGIN_MAX_FAILURES):
            APIClient().post(LOGIN, {"email": "a@example.com", "password": "wrong-secret-9"})

        response = APIClient().post(LOGIN, {"email": "a@example.com", "password": PASSWORD})

        assert response.status_code == 429
        reasons = [log.detail["reason"] for log in logs(Action.LOGIN_FAILURE)]
        assert reasons[-1] == "locked"
        assert reasons.count("invalid_credentials") == settings.LOGIN_MAX_FAILURES
        assert logs(Action.LOGIN_SUCCESS) == []


class TestAdminChanges:
    def test_grant_records_one_row_per_changed_user(self):
        admin, target, already = make_user("admin", True), make_user("t"), make_user("al", True)

        response = api(admin).post(ADMINS, {"user_ids": [target.id, already.id]}, format="json")

        assert response.status_code == 204
        rows = logs(Action.ADMIN_GRANT)
        # すでに管理者だったユーザーは、変わっていないので、記録しない
        assert [(r.actor, r.target_id, r.detail) for r in rows] == [
            (admin, str(target.id), {"email": "t@example.com"})
        ]
        assert rows[0].ip == "127.0.0.1"

    def test_revoke_records_the_changed_user(self):
        admin, other = make_user("admin", True), make_user("other", True)

        response = api(admin).post(REVOKE, {"user_ids": [other.id]}, format="json")

        assert response.status_code == 204
        rows = logs(Action.ADMIN_REVOKE)
        assert [(r.actor, r.target_id) for r in rows] == [(admin, str(other.id))]

    def test_a_refused_change_is_not_recorded(self):
        admin = make_user("admin", True)

        response = api(admin).post(REVOKE, {"user_ids": [admin.id]}, format="json")

        assert response.status_code == 400 or response.status_code == 409
        assert logs(Action.ADMIN_REVOKE) == []


class TestPolicyReplace:
    def upload_and_process(self, admin, samples, name):
        data = (samples / name).read_bytes()
        accept_upload(SimpleUploadedFile(name, data), admin)
        process_policy(claim_next())

    def test_first_registration_has_no_old_filename(self, samples):
        admin = make_user("admin", True)

        self.upload_and_process(admin, samples, "dummy_policy.pdf")

        log = logs(Action.POLICY_REPLACE)[0]
        assert log.actor == admin and log.ip is None
        assert log.detail == {
            "old_filename": None,
            "new_filename": "dummy_policy.pdf",
            "page_count": 3,
        }

    def test_replacing_records_the_old_and_new_filenames(self, samples):
        admin = make_user("admin", True)
        self.upload_and_process(admin, samples, "dummy_policy.pdf")

        self.upload_and_process(admin, samples, "dummy_policy_revised.pdf")

        log = logs(Action.POLICY_REPLACE)[-1]
        assert log.detail["old_filename"] == "dummy_policy.pdf"
        assert log.detail["new_filename"] == "dummy_policy_revised.pdf"

    def test_a_failed_processing_is_not_recorded(self, samples):
        admin = make_user("admin", True)
        accept_upload(SimpleUploadedFile("broken.pdf", b"%PDF-1.4 broken"), admin)

        process_policy(claim_next())

        assert logs(Action.POLICY_REPLACE) == []


class TestUsersImport:
    def write(self, tmp_path, text, name="users.csv"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_records_only_the_counts_and_the_filename(self, tmp_path):
        make_user("exists")
        path = self.write(tmp_path, "email,name\na@example.com,A\nexists@example.com,E\nbad,B\n")

        with pytest.raises(CommandError):
            call_command("import_users", path)

        log = logs(Action.USERS_IMPORT)[0]
        assert log.actor is None and log.ip is None
        assert log.detail == {"filename": "users.csv", "created": 1, "skipped": 1, "errors": 1}
        assert "a@example.com" not in dump(log)

    def test_dry_run_and_atomic_abort_are_not_recorded(self, tmp_path):
        path = self.write(tmp_path, "email,name\na@example.com,A\nbad,B\n")
        valid = self.write(tmp_path, "email,name\nc@example.com,C\n", name="valid.csv")

        call_command("import_users", valid, dry_run=True)
        with pytest.raises(CommandError):
            call_command("import_users", path, atomic=True)

        assert logs(Action.USERS_IMPORT) == []


class TestAuditLogApi:
    URL = "/api/v1/admin/audit-logs"

    def test_requires_admin(self):
        assert api().get(self.URL).status_code == 401
        assert api(make_user("normal")).get(self.URL).status_code == 403
        assert api(make_user("admin", is_admin=True)).get(self.URL).status_code == 200

    def test_lists_newest_first_with_fields(self):
        admin = make_user("admin", is_admin=True)
        record(Action.LOGIN_FAILURE, actor_email="x@example.com")
        record(
            Action.ADMIN_GRANT,
            actor=admin,
            actor_email=admin.email,
            target_type="user",
            target_id=5,
            detail={"email": "b@example.com"},
        )

        body = api(admin).get(self.URL).json()

        assert body["count"] == 2
        first, second = body["results"]
        assert first["action"] == "admin.grant"
        assert first["action_label"] == "管理者権限の付与"
        assert first["actor_email"] == "admin@example.com"
        assert first["actor_name"] == "admin"
        assert first["target_type"] == "user"
        assert first["target_id"] == "5"
        assert first["detail"] == {"email": "b@example.com"}
        assert second["action"] == "login.failure"
        assert second["actor_name"] == ""

    def test_includes_action_choices(self):
        body = api(make_user("admin", is_admin=True)).get(self.URL).json()

        assert {"value": "login.failure", "label": "ログイン失敗"} in body["actions"]
        assert len(body["actions"]) == len(Action.choices)

    def test_paginates(self):
        admin = make_user("admin", is_admin=True)
        for _ in range(3):
            record(Action.LOGIN_FAILURE, actor_email="x@example.com")

        body = api(admin).get(self.URL, {"page_size": 2, "page": 2}).json()

        assert (body["count"], body["page"], body["page_size"]) == (3, 2, 2)
        assert len(body["results"]) == 1

    def test_filters_by_action(self):
        admin = make_user("admin", is_admin=True)
        record(Action.LOGIN_FAILURE, actor_email="x@example.com")
        record(Action.LOGIN_SUCCESS, actor=admin, actor_email=admin.email)

        body = api(admin).get(self.URL, {"action": "login.success"}).json()

        assert [r["action"] for r in body["results"]] == ["login.success"]

    def test_invalid_action_gets_400(self):
        response = api(make_user("admin", is_admin=True)).get(self.URL, {"action": "nope"})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_is_read_only(self):
        client = api(make_user("admin", is_admin=True))

        for method in (client.post, client.put, client.patch, client.delete):
            assert method(self.URL).status_code == 405
