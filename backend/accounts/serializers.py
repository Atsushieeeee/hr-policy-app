from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_admin"]
        read_only_fields = fields


class AdminUserSerializer(serializers.ModelSerializer):
    """管理画面の一覧に出す、ユーザーの情報。"""

    class Meta:
        model = User
        fields = ["id", "name", "email", "created_at"]
        read_only_fields = fields


class UserIdsSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_user_ids(self, value):
        return list(dict.fromkeys(value))  # 重複を除く（順序は保つ）
