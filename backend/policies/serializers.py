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
