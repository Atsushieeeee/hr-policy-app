from rest_framework import serializers

from .models import PolicyDocument


class UploadSerializer(serializers.ModelSerializer):
    """アップロードの受け付け結果（処理中・失敗の状況）。"""

    class Meta:
        model = PolicyDocument
        fields = [
            "id",
            "title",
            "original_filename",
            "file_size",
            "status",
            "error_code",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class CurrentPolicySerializer(serializers.ModelSerializer):
    """現行の規程。"""

    uploaded_by = serializers.SerializerMethodField()
    uploaded_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = PolicyDocument
        fields = [
            "id",
            "title",
            "original_filename",
            "file_size",
            "page_count",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = fields

    def get_uploaded_by(self, obj):
        return {"id": obj.uploaded_by_id, "name": obj.uploaded_by.name}


class LatestUploadSerializer(UploadSerializer):
    """処理中、または直近で失敗した取り込み。"""

    class Meta(UploadSerializer.Meta):
        fields = [*UploadSerializer.Meta.fields, "updated_at"]
        read_only_fields = fields
