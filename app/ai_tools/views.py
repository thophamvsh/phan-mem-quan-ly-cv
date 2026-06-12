import logging
import json
import time

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import CanUseAiTools
from .serializers import AiChatRequestSerializer
from .services import AiToolsError, run_ai_chat
from .storage import delete_session, get_conversation, get_sessions


logger = logging.getLogger(__name__)


def _sse_event(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _response_chunks(text, chunk_size=80):
    text = str(text or "")
    for start in range(0, len(text), chunk_size):
        yield text[start:start + chunk_size]


def stream_ai_chat(*, user, content, session_id=None):
    yield _sse_event("status", {"message": "Đang xử lý yêu cầu..."})
    try:
        data = run_ai_chat(
            user=user,
            content=content,
            session_id=session_id,
        )
    except AiToolsError as exc:
        yield _sse_event("error", {"detail": str(exc), "status": 503})
        return
    except Exception:
        logger.exception("AI chat stream request failed")
        yield _sse_event("error", {"detail": "Khong the xu ly yeu cau AI luc nay.", "status": 500})
        return

    for chunk in _response_chunks(data.get("response", "")):
        yield _sse_event("delta", {"text": chunk})
        time.sleep(0.02)

    yield _sse_event("done", data)


class AiChatAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request):
        serializer = AiChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("stream"):
            response = StreamingHttpResponse(
                stream_ai_chat(
                    user=request.user,
                    content=serializer.validated_data["content"],
                    session_id=serializer.validated_data.get("session_id") or None,
                ),
                content_type="text/event-stream",
            )
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            return response

        try:
            data = run_ai_chat(
                user=request.user,
                content=serializer.validated_data["content"],
                session_id=serializer.validated_data.get("session_id") or None,
            )
        except AiToolsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.exception("AI chat request failed")
            return Response({"detail": "Khong the xu ly yeu cau AI luc nay."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(data)


class AiChatStreamAPIView(APIView):
    permission_classes = [CanUseAiTools]

    def post(self, request):
        serializer = AiChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = StreamingHttpResponse(
            stream_ai_chat(
                user=request.user,
                content=serializer.validated_data["content"],
                session_id=serializer.validated_data.get("session_id") or None,
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


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
