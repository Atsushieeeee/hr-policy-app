from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, name, password=None, is_admin=False):
        if not email:
            raise ValueError("メールアドレスは必須です。")
        user = self.model(email=self.normalize(email), name=name, is_admin=is_admin)
        # password が None の場合は、ログインできない状態（使用不可のパスワード）になる
        user.set_password(password)
        user.save(using=self._db)
        return user

    @staticmethod
    def normalize(email):
        # メールアドレスは大文字小文字を区別せず、小文字で統一する
        return email.strip().lower()

    def get_by_natural_key(self, email):
        return self.get(email=self.normalize(email))


class User(AbstractBaseUser):
    """ログインユーザー。権限は is_admin だけで判定する（Django管理サイトは使わない）。"""

    email = models.EmailField(max_length=254, unique=True)
    name = models.CharField(max_length=100)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return self.email
