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
