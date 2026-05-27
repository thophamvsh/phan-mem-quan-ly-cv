import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import CanUseAiTools
from .serializers import AiChatRequestSerializer
from .services import AiToolsError, run_ai_chat
from .storage import delete_session, get_conversation, get_sessions


logger = logging.getLogger(__name__)


class AiChatAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request):
        serializer = AiChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = run_ai_chat(
                user=request.user,
                content=serializer.validated_data["content"],
                session_id=serializer.validated_data.get("session_id") or None,
                provider=serializer.validated_data.get("provider") or "openai",
                model=serializer.validated_data.get("model") or "",
            )
        except AiToolsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.exception("AI chat request failed")
            return Response({"detail": "Khong the xu ly yeu cau AI luc nay."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(data)


class AiChatSessionsAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def get(self, request):
        limit = int(request.query_params.get("limit") or 50)
        limit = max(1, min(limit, 200))
        return Response({"sessions": get_sessions(request.user, limit=limit)})


class AiChatHistoryAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response({"detail": "session_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "session_id": session_id,
                "messages": get_conversation(request.user, session_id, limit=200),
            }
        )

    def delete(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response({"detail": "session_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"session_id": session_id, "deleted": delete_session(request.user, session_id)})
