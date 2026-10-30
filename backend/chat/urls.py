from django.urls import path

from .views import ChatCurrentSessionView, ChatMessageView, ChatSessionView

urlpatterns = [
    path("chat/messages", ChatMessageView.as_view(), name="chat-messages"),
    path("chat/sessions", ChatSessionView.as_view(), name="chat-sessions"),
    path("chat/sessions/current", ChatCurrentSessionView.as_view(), name="chat-sessions-current"),
]
