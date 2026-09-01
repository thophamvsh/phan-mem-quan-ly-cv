import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Keep every DRF failure JSON while preserving normal DRF field errors."""
    if isinstance(exc, DjangoValidationError):
        detail = getattr(exc, "message_dict", None) or getattr(
            exc,
            "messages",
            [str(exc)],
        )
        exc = ValidationError(detail=detail)

    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, IntegrityError):
        logger.warning("Database integrity error in API request", exc_info=exc)
        return Response(
            {
                "detail": "Dữ liệu bị trùng hoặc đang được bản ghi khác sử dụng.",
                "code": "integrity_error",
            },
            status=status.HTTP_409_CONFLICT,
        )

    logger.exception("Unhandled API exception", exc_info=exc)
    return Response(
        {
            "detail": "Lỗi máy chủ nội bộ.",
            "code": "server_error",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
