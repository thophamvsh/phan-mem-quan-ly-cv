from django.urls import path

from .views import AiChatAPIView, AiChatHistoryAPIView, AiChatSessionsAPIView, AiChatStreamAPIView


urlpatterns = [
    path("chat/", AiChatAPIView.as_view(), name="ai-tools-chat"),
    path("chat/stream/", AiChatStreamAPIView.as_view(), name="ai-tools-chat-stream"),
    path("chat/sessions/", AiChatSessionsAPIView.as_view(), name="ai-tools-chat-sessions"),
    path("chat/history/", AiChatHistoryAPIView.as_view(), name="ai-tools-chat-history"),
]
