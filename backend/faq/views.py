from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.services import record
from core.pagination import StandardPagination
from core.views import AdminAPIView

from .models import FAQ
from .serializers import (
    FAQCreateSerializer,
    FAQSerializer,
    FAQUpdateSerializer,
    PublicFAQListSerializer,
    PublicFAQSerializer,
)
from .services import (
    candidate_details,
    candidate_groups,
    current_policy_snapshot,
    next_sort_order,
    publish_reviewed,
)


def record_faq(request, action, faq, detail=None):
    record(
        action,
        actor=request.user,
        request=request,
        target_type="faq",
        target_id=faq.id,
        detail={"question": faq.question, **(detail or {})},
    )


class FAQCandidateListView(AdminAPIView):
    """FAQにする候補（よく聞かれている質問）の一覧。?include_registered=true で、登録済みも含める。

    質問者を特定できる情報（名前、メールアドレス、ユーザーID）は、返さない。
    """

    def get(self, request):
        include_registered = request.query_params.get("include_registered") == "true"
        paginator = StandardPagination()
        page = paginator.paginate_queryset(candidate_groups(include_registered), request)
        return paginator.get_paginated_response(candidate_details(page))


class FAQListView(AdminAPIView):
    """FAQの一覧（全状態、並び順どおり）。?status= で絞り込む。登録（POST）もここで行う。"""

    def get(self, request):
        faqs = FAQ.objects.all()
        status_filter = request.query_params.get("status", "")
        if status_filter:
            if status_filter not in FAQ.Status.values:
                raise serializers.ValidationError({"status": "状態が正しくありません。"})
            faqs = faqs.filter(status=status_filter)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(faqs, request)
        return paginator.get_paginated_response(FAQSerializer(page, many=True).data)

    def post(self, request):
        serializer = FAQCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        faq = FAQ.objects.create(
            question=data["question"],
            answer=data["answer"],
            sources=data.get("sources", []),
            sort_order=next_sort_order(),
            source_message_id=data.get("source_message_id"),
            policy_snapshot=current_policy_snapshot(),
            created_by=request.user,
        )
        record_faq(request, AuditLog.Action.FAQ_CREATE, faq)
        return Response(FAQSerializer(faq).data, status=status.HTTP_201_CREATED)


class FAQDetailView(AdminAPIView):
    """編集（PATCH）と、削除（DELETE）。"""

    def patch(self, request, pk):
        faq = get_object_or_404(FAQ, pk=pk)
        serializer = FAQUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        was_published = faq.status == FAQ.Status.PUBLISHED
        for field, value in serializer.validated_data.items():
            setattr(faq, field, value)
        faq.save()
        if faq.status == FAQ.Status.PUBLISHED and not was_published:
            record_faq(request, AuditLog.Action.FAQ_PUBLISH, faq)
        return Response(FAQSerializer(faq).data)

    def delete(self, request, pk):
        faq = get_object_or_404(FAQ, pk=pk)
        record_faq(request, AuditLog.Action.FAQ_DELETE, faq)
        faq.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FAQPublishReviewedView(AdminAPIView):
    """「要確認」のFAQを、すべて公開に戻す。"""

    def post(self, request):
        count = publish_reviewed()
        if count:
            record(
                AuditLog.Action.FAQ_PUBLISH,
                actor=request.user,
                request=request,
                target_type="faq",
                detail={"count": count, "reviewed": True},
            )
        return Response({"count": count})


class PublicFAQListView(APIView):
    """公開中のFAQの一覧（質問だけ、並び順どおり）。ログイン済みなら、管理者権限の有無に関わらず使える。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        faqs = FAQ.objects.filter(status=FAQ.Status.PUBLISHED)
        return Response(PublicFAQListSerializer(faqs, many=True).data)


class PublicFAQDetailView(APIView):
    """公開中のFAQの質問・回答・根拠。AIは呼ばない。開くたびに、表示回数を増やす。

    公開していないFAQは、存在しない場合と同じく404にする（存在を知らせない）。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        faq = get_object_or_404(FAQ, pk=pk, status=FAQ.Status.PUBLISHED)
        # 同時に開かれても数え落とさないよう、DB側で加算する
        FAQ.objects.filter(pk=faq.pk).update(view_count=F("view_count") + 1)
        return Response(PublicFAQSerializer(faq).data)
