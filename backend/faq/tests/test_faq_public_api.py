import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from faq.models import FAQ

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
URL = "/api/v1/faqs"
SOURCES = [{"policy_id": 1, "article": "第7条", "page": 2}]


@pytest.fixture
def author():
    return User.objects.create_user(
        email="admin@example.com", name="管理者", password=PASSWORD, is_admin=True
    )


@pytest.fixture
def employee():
    client = APIClient()
    user = User.objects.create_user(email="emp@example.com", name="社員", password=PASSWORD)
    client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)))
    return client


def make_faq(author, question="質問", status=FAQ.Status.PUBLISHED, sort_order=0):
    return FAQ.objects.create(
        question=question,
        answer="回答",
        sources=SOURCES,
        status=status,
        sort_order=sort_order,
        created_by=author,
    )


class TestAuth:
    @pytest.mark.parametrize("path", [URL, f"{URL}/1"])
    def test_requires_login(self, path):
        assert APIClient().get(path).status_code == 401

    def test_employee_can_read(self, employee, author):
        faq = make_faq(author)
        assert employee.get(URL).status_code == 200
        assert employee.get(f"{URL}/{faq.id}").status_code == 200


class TestList:
    def test_only_published_in_order_with_question_only(self, employee, author):
        make_faq(author, "二番目", sort_order=2)
        make_faq(author, "一番目", sort_order=1)
        make_faq(author, "下書き", status=FAQ.Status.DRAFT)
        make_faq(author, "要確認", status=FAQ.Status.NEEDS_REVIEW)
        data = employee.get(URL).json()
        assert [f["question"] for f in data] == ["一番目", "二番目"]
        assert set(data[0]) == {"id", "question"}

    def test_empty(self, employee):
        assert employee.get(URL).json() == []

    def test_does_not_count_views(self, employee, author):
        faq = make_faq(author)
        employee.get(URL)
        faq.refresh_from_db()
        assert faq.view_count == 0

    def test_replacing_the_policy_hides_faqs(self, employee, author):
        from faq.services import mark_published_for_review

        make_faq(author)
        mark_published_for_review()
        assert employee.get(URL).json() == []


class TestDetail:
    def test_returns_public_fields_only(self, employee, author):
        faq = make_faq(author)
        data = employee.get(f"{URL}/{faq.id}").json()
        assert data == {"id": faq.id, "question": "質問", "answer": "回答", "sources": SOURCES}

    def test_counts_each_view(self, employee, author):
        faq = make_faq(author)
        employee.get(f"{URL}/{faq.id}")
        employee.get(f"{URL}/{faq.id}")
        faq.refresh_from_db()
        assert faq.view_count == 2

    @pytest.mark.parametrize("status", [FAQ.Status.DRAFT, FAQ.Status.NEEDS_REVIEW])
    def test_unpublished_is_404_and_not_counted(self, employee, author, status):
        faq = make_faq(author, status=status)
        response = employee.get(f"{URL}/{faq.id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
        faq.refresh_from_db()
        assert faq.view_count == 0

    def test_missing_is_404(self, employee):
        assert employee.get(f"{URL}/999").status_code == 404
