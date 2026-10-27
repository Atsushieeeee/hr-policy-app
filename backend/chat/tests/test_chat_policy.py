from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from policies.models import PolicyDocument
from policies.services import accept_upload, claim_next, process_policy

pytestmark = pytest.mark.django_db

URL = "/api/v1/chat/messages"


@pytest.fixture
def user():
    return User.objects.create_user(
        email="taro@example.com", name="太郎", password="valid-password-2026"
    )


def ask(client, user, question="有給休暇は何日ですか？"):
    return client.post(
        URL,
        data={"question": question},
        content_type="application/json",
        HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)),
    )


def register(samples, admin, name):
    data = (samples / name).read_bytes()
    accept_upload(SimpleUploadedFile(name, data, content_type="application/pdf"), admin)
    process_policy(claim_next())


def test_answers_based_on_the_registered_policy(client, user, registered_policy):
    with patch("chat.views.get_rag_client") as get_client:
        get_client.return_value.answer.return_value.text = "回答"
        get_client.return_value.answer.return_value.found = True
        get_client.return_value.answer.return_value.sources = []
        response = ask(client, user)

    assert response.status_code == 200
    get_client.return_value.answer.assert_called_once_with(
        "有給休暇は何日ですか？", registered_policy.extracted_text
    )


def test_returns_409_without_calling_ai_when_no_policy_is_registered(client, user):
    with patch("chat.views.get_rag_client") as get_client:
        response = ask(client, user)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "POLICY_NOT_REGISTERED"
    get_client.assert_not_called()


def test_policy_still_processing_is_not_used(client, user, samples):
    admin = User.objects.create_user(
        email="admin@example.com", name="管理者", password="valid-password-2026", is_admin=True
    )
    data = (samples / "dummy_policy.pdf").read_bytes()
    accept_upload(SimpleUploadedFile("p.pdf", data, content_type="application/pdf"), admin)

    with patch("chat.views.get_rag_client") as get_client:
        response = ask(client, user)

    assert response.status_code == 409
    get_client.assert_not_called()


def test_answers_with_the_new_policy_after_replacement(client, user, samples):
    admin = User.objects.create_user(
        email="admin@example.com", name="管理者", password="valid-password-2026", is_admin=True
    )
    register(samples, admin, "dummy_policy.pdf")
    first = PolicyDocument.objects.get(status=PolicyDocument.Status.READY).extracted_text

    register(samples, admin, "dummy_policy_revised.pdf")
    second = PolicyDocument.objects.get(status=PolicyDocument.Status.READY).extracted_text

    with patch("chat.views.get_rag_client") as get_client:
        get_client.return_value.answer.return_value.text = "回答"
        get_client.return_value.answer.return_value.found = True
        get_client.return_value.answer.return_value.sources = []
        ask(client, user)

    assert first != second
    assert get_client.return_value.answer.call_args.args[1] == second
