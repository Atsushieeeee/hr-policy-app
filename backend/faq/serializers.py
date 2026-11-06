from rest_framework import serializers

from chat.models import ChatMessage

from .models import FAQ

MAX_QUESTION_LENGTH = 1000


class SourceSerializer(serializers.Serializer):
    policy_id = serializers.IntegerField(min_value=1)
    article = serializers.CharField(max_length=100, allow_blank=True)
    page = serializers.IntegerField(min_value=1)


class FAQSerializer(serializers.ModelSerializer):
    """管理画面に出す、FAQの情報。"""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_message_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = FAQ
        fields = [
            "id",
            "question",
            "answer",
            "sources",
            "status",
            "status_label",
            "sort_order",
            "source_message_id",
            "policy_snapshot",
            "view_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class FAQCreateSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH)
    answer = serializers.CharField()
    sources = SourceSerializer(many=True, required=False, max_length=20)
    # 指定すると、そのチャット（回答）の根拠を引き継ぐ（sources は、使わない）
    source_message_id = serializers.IntegerField(min_value=1, required=False)

    def validate_source_message_id(self, value):
        message = ChatMessage.objects.filter(id=value, role=ChatMessage.Role.ASSISTANT).first()
        if message is None:
            raise serializers.ValidationError("元になるチャット（回答）が見つかりません。")
        self._source_message = message
        return value

    def validate(self, attrs):
        message = getattr(self, "_source_message", None)
        if message is not None:
            attrs["sources"] = message.sources
        return attrs


class FAQUpdateSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH, required=False)
    answer = serializers.CharField(required=False)
    # 「要確認」にできるのは、規程の置き換えだけ
    status = serializers.ChoiceField(
        choices=[FAQ.Status.DRAFT, FAQ.Status.PUBLISHED], required=False
    )
    sort_order = serializers.IntegerField(min_value=0, required=False)
