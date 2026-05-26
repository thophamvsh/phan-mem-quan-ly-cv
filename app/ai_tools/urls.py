from django.urls import path

from .views import AiChatAPIView, AiChatHistoryAPIView, AiChatSessionsAPIView


urlpatterns = [
    path("chat/", AiChatAPIView.as_view(), name="ai-tools-chat"),
    path("chat/sessions/", AiChatSessionsAPIView.as_view(), name="ai-tools-chat-sessions"),
    path("chat/history/", AiChatHistoryAPIView.as_view(), name="ai-tools-chat-history"),
]
