import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from audit.models import AuditLog
from chat.models import ChatMessage, ChatSession
from faq.models import FAQ
from policies.models import PolicyDocument
from policies.services import accept_upload, claim_next, process_policy

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
URL = "/api/v1/admin/faqs"
Action = AuditLog.Action
SOURCES = [{"policy_id": 1, "article": "第7条", "page": 2}]


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com", name="管理者", password=PASSWORD, is_admin=True
    )


@pytest.fixture
def admin(admin_user):
    client = APIClient()
    client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(admin_user)))
    return client


def make_faq(admin_user, question="質問", status=FAQ.Status.DRAFT, sort_order=0):
    return FAQ.objects.create(
        question=question,
        answer="回答",
        status=status,
        sort_order=sort_order,
        created_by=admin_user,
    )


def make_message(admin_user, role=ChatMessage.Role.ASSISTANT, sources=None):
    session = ChatSession.objects.create(user=admin_user)
    return ChatMessage.objects.create(
        session=session, role=role, content="本文", sources=sources if sources is not None else []
    )


def post(admin, **body):
    data = {"question": "有給は何日？", "answer": "10日です。", **body}
    return admin.post(URL, data, format="json")


def logs(action):
    return list(AuditLog.objects.filter(action=action).order_by("id"))


class TestCreate:
    def test_creates_a_draft_at_the_end(self, admin, admin_user):
        make_faq(admin_user, sort_order=4)

        response = post(admin, sources=SOURCES)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "draft"
        assert body["status_label"] == "下書き"
        assert body["sort_order"] == 5
        assert body["sources"] == SOURCES
        assert body["view_count"] == 0
        assert FAQ.objects.get(id=body["id"]).created_by == admin_user

    def test_first_faq_starts_at_zero(self, admin):
        assert post(admin).json()["sort_order"] == 0

    def test_inherits_sources_from_the_source_message(self, admin, admin_user):
        message = make_message(admin_user, sources=SOURCES)

        body = post(admin, source_message_id=message.id).json()

        assert body["source_message_id"] == message.id
        assert body["sources"] == SOURCES

    def test_source_message_takes_precedence_over_sources(self, admin, admin_user):
        message = make_message(admin_user, sources=SOURCES)
        other = [{"policy_id": 1, "article": "第9条", "page": 3}]

        body = post(admin, source_message_id=message.id, sources=other).json()

        assert body["sources"] == SOURCES

    @pytest.mark.parametrize("kind", ["question_message", "missing"])
    def test_rejects_an_invalid_source_message(self, admin, admin_user, kind):
        if kind == "question_message":
            message_id = make_message(admin_user, role=ChatMessage.Role.USER).id
        else:
            message_id = 9999

        response = post(admin, source_message_id=message_id)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert FAQ.objects.count() == 0

    @pytest.mark.parametrize(
        "body",
        [
            {"question": ""},
            {"answer": ""},
            {"question": "あ" * 1001},
            {"sources": [{"policy_id": 1, "article": "第7条"}]},
        ],
    )
    def test_rejects_invalid_input(self, admin, body):
        assert post(admin, **body).status_code == 400

    def test_records_the_current_policy(self, admin, admin_user, samples):
        data = (samples / "dummy_policy.pdf").read_bytes()
        accept_upload(SimpleUploadedFile("a.pdf", data), admin_user)
        process_policy(claim_next())
        policy = PolicyDocument.objects.get()

        body = post(admin).json()

        assert body["policy_snapshot"] == {"policy_id": policy.id, "sha256": policy.sha256}

    def test_snapshot_is_empty_without_a_policy(self, admin):
        assert post(admin).json()["policy_snapshot"] == {}

    def test_is_audited(self, admin, admin_user):
        post(admin)

        (log,) = logs(Action.FAQ_CREATE)
        assert log.actor == admin_user
        assert (log.target_type, log.detail["question"]) == ("faq", "有給は何日？")


class TestList:
    def test_orders_by_sort_order_and_filters_by_status(self, admin, admin_user):
        make_faq(admin_user, "b", FAQ.Status.PUBLISHED, sort_order=2)
        make_faq(admin_user, "a", FAQ.Status.DRAFT, sort_order=1)
        make_faq(admin_user, "c", FAQ.Status.NEEDS_REVIEW, sort_order=3)

        everything = admin.get(URL).json()
        published = admin.get(URL, {"status": "published"}).json()

        assert [f["question"] for f in everything["results"]] == ["a", "b", "c"]
        assert everything["count"] == 3
        assert [f["question"] for f in published["results"]] == ["b"]

    def test_invalid_status_gets_400(self, admin):
        assert admin.get(URL, {"status": "nope"}).status_code == 400

    def test_paginates(self, admin, admin_user):
        for i in range(3):
            make_faq(admin_user, f"q{i}", sort_order=i)

        body = admin.get(URL, {"page_size": 2, "page": 2}).json()

        assert (body["count"], body["page"], body["page_size"]) == (3, 2, 2)
        assert len(body["results"]) == 1


class TestUpdate:
    def test_edits_fields(self, admin, admin_user):
        faq = make_faq(admin_user)

        response = admin.patch(
            f"{URL}/{faq.id}",
            {"question": "新しい質問", "answer": "新しい回答", "sort_order": 7},
            format="json",
        )

        assert response.status_code == 200
        faq.refresh_from_db()
        assert (faq.question, faq.answer, faq.sort_order) == ("新しい質問", "新しい回答", 7)
        assert faq.status == FAQ.Status.DRAFT

    def test_publishing_is_audited_once(self, admin, admin_user):
        faq = make_faq(admin_user)

        admin.patch(f"{URL}/{faq.id}", {"status": "published"}, format="json")
        admin.patch(f"{URL}/{faq.id}", {"status": "published"}, format="json")

        faq.refresh_from_db()
        assert faq.status == FAQ.Status.PUBLISHED
        assert len(logs(Action.FAQ_PUBLISH)) == 1

    def test_unpublishing_returns_to_draft(self, admin, admin_user):
        faq = make_faq(admin_user, status=FAQ.Status.PUBLISHED)

        admin.patch(f"{URL}/{faq.id}", {"status": "draft"}, format="json")

        faq.refresh_from_db()
        assert faq.status == FAQ.Status.DRAFT
        assert logs(Action.FAQ_PUBLISH) == []

    def test_a_needs_review_faq_can_be_published_by_editing(self, admin, admin_user):
        faq = make_faq(admin_user, status=FAQ.Status.NEEDS_REVIEW)

        admin.patch(f"{URL}/{faq.id}", {"status": "published"}, format="json")

        faq.refresh_from_db()
        assert faq.status == FAQ.Status.PUBLISHED
        assert len(logs(Action.FAQ_PUBLISH)) == 1

    @pytest.mark.parametrize(
        "body", [{"status": "needs_review"}, {"status": "nope"}, {"answer": ""}, {"sort_order": -1}]
    )
    def test_rejects_invalid_input(self, admin, admin_user, body):
        faq = make_faq(admin_user)

        assert admin.patch(f"{URL}/{faq.id}", body, format="json").status_code == 400

    def test_unknown_id_gets_404(self, admin):
        response = admin.patch(f"{URL}/999", {"answer": "x"}, format="json")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_ignores_fields_that_cannot_be_edited(self, admin, admin_user):
        faq = make_faq(admin_user)

        admin.patch(f"{URL}/{faq.id}", {"view_count": 99, "sources": SOURCES}, format="json")

        faq.refresh_from_db()
        assert (faq.view_count, faq.sources) == (0, [])


class TestDelete:
    def test_deletes_and_audits(self, admin, admin_user):
        faq = make_faq(admin_user, "消す質問")

        response = admin.delete(f"{URL}/{faq.id}")

        assert response.status_code == 204
        assert not FAQ.objects.filter(id=faq.id).exists()
        (log,) = logs(Action.FAQ_DELETE)
        assert log.detail["question"] == "消す質問"

    def test_unknown_id_gets_404(self, admin):
        assert admin.delete(f"{URL}/999").status_code == 404

    def test_source_message_can_be_deleted_without_deleting_the_faq(self, admin_user):
        message = make_message(admin_user)
        faq = FAQ.objects.create(
            question="q", answer="a", source_message=message, created_by=admin_user
        )

        ChatSession.objects.all().delete()

        faq.refresh_from_db()
        assert faq.source_message is None


class TestPublishReviewed:
    def test_publishes_only_needs_review(self, admin, admin_user):
        reviewed = make_faq(admin_user, status=FAQ.Status.NEEDS_REVIEW)
        draft = make_faq(admin_user, status=FAQ.Status.DRAFT)

        response = admin.post(f"{URL}/publish-reviewed")

        assert response.json() == {"count": 1}
        reviewed.refresh_from_db()
        draft.refresh_from_db()
        assert reviewed.status == FAQ.Status.PUBLISHED
        assert draft.status == FAQ.Status.DRAFT
        (log,) = logs(Action.FAQ_PUBLISH)
        assert log.detail == {"count": 1, "reviewed": True}

    def test_nothing_to_publish_is_not_audited(self, admin):
        response = admin.post(f"{URL}/publish-reviewed")

        assert response.json() == {"count": 0}
        assert logs(Action.FAQ_PUBLISH) == []


class TestPolicyReplacement:
    def register(self, admin_user, samples, name):
        accept_upload(SimpleUploadedFile(name, (samples / name).read_bytes()), admin_user)
        process_policy(claim_next())

    def test_replacing_the_policy_marks_published_faqs_for_review(self, admin_user, samples):
        self.register(admin_user, samples, "dummy_policy.pdf")
        published = make_faq(admin_user, status=FAQ.Status.PUBLISHED)
        draft = make_faq(admin_user, status=FAQ.Status.DRAFT)

        self.register(admin_user, samples, "dummy_policy_revised.pdf")

        published.refresh_from_db()
        draft.refresh_from_db()
        assert published.status == FAQ.Status.NEEDS_REVIEW
        assert draft.status == FAQ.Status.DRAFT
        (log,) = logs(Action.FAQ_NEEDS_REVIEW)
        assert log.detail == {"count": 1}
        assert log.actor == admin_user

    def test_no_audit_when_no_faq_is_published(self, admin_user, samples):
        make_faq(admin_user, status=FAQ.Status.DRAFT)

        self.register(admin_user, samples, "dummy_policy.pdf")

        assert logs(Action.FAQ_NEEDS_REVIEW) == []

    def test_a_failed_replacement_keeps_published_faqs(self, admin_user, samples):
        self.register(admin_user, samples, "dummy_policy.pdf")
        published = make_faq(admin_user, status=FAQ.Status.PUBLISHED)

        accept_upload(
            SimpleUploadedFile("no_text.pdf", (samples / "invalid/no_text.pdf").read_bytes()),
            admin_user,
        )
        process_policy(claim_next())

        published.refresh_from_db()
        assert published.status == FAQ.Status.PUBLISHED
