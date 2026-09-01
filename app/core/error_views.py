from django.http import JsonResponse
from django.views import defaults


def _is_api_request(request):
    return request.path.startswith("/api/")


def bad_request(request, exception):
    if not _is_api_request(request):
        return defaults.bad_request(request, exception)
    return JsonResponse(
        {"detail": "Yêu cầu không hợp lệ.", "code": "bad_request"},
        status=400,
    )


def permission_denied(request, exception):
    if not _is_api_request(request):
        return defaults.permission_denied(request, exception)
    return JsonResponse(
        {"detail": "Bạn không có quyền thực hiện thao tác này.", "code": "permission_denied"},
        status=403,
    )


def page_not_found(request, exception):
    if not _is_api_request(request):
        return defaults.page_not_found(request, exception)
    return JsonResponse(
        {"detail": "Không tìm thấy API được yêu cầu.", "code": "not_found"},
        status=404,
    )


def server_error(request):
    if not _is_api_request(request):
        return defaults.server_error(request)
    return JsonResponse(
        {"detail": "Lỗi máy chủ nội bộ.", "code": "server_error"},
        status=500,
    )
