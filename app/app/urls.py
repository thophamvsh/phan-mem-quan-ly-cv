"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from core.auth_views import health_check

handler400 = "core.error_views.bad_request"
handler403 = "core.error_views.permission_denied"
handler404 = "core.error_views.page_not_found"
handler500 = "core.error_views.server_error"

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('admin/', admin.site.urls),

    # Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Legacy API routes (backward compatibility)
    path('api/', include('core.urls')),
    path("api/khovattu/", include(("khovattu.urls", "khovattu"), namespace="legacy-khovattu")),
    path("api/nhatkyvanhanh/", include(("nhatkyvanhanh.urls", "nhatkyvanhanh"), namespace="legacy-nhatkyvanhanh")),
    path("api/quanlyvanhanh/", include(("quanlyvanhanh.urls", "quanlyvanhanh"), namespace="legacy-quanlyvanhanh")),
    path("api/quanlycatruc/", include(("quanlycatruc.urls", "quanlycatruc"), namespace="legacy-quanlycatruc")),
    path("api/ai/", include("ai_tools.urls")),
    path("api/documents/", include("documents.urls")),

    # Versioned API routes (v1)
    path('api/v1/', include('core.urls')),
    path("api/v1/khovattu/", include(("khovattu.urls", "khovattu"), namespace="v1-khovattu")),
    path("api/v1/nhatkyvanhanh/", include(("nhatkyvanhanh.urls", "nhatkyvanhanh"), namespace="v1-nhatkyvanhanh")),
    path("api/v1/quanlyvanhanh/", include(("quanlyvanhanh.urls", "quanlyvanhanh"), namespace="v1-quanlyvanhanh")),
    path("api/v1/quanlycatruc/", include(("quanlycatruc.urls", "quanlycatruc"), namespace="v1-quanlycatruc")),
    path("api/tochuc/", include(("tochuc.urls", "tochuc"), namespace="legacy-tochuc")),
    path("api/v1/tochuc/", include(("tochuc.urls", "tochuc"), namespace="v1-tochuc")),
    path("api/v1/ai/", include("ai_tools.urls")),
    path("api/v1/documents/", include("documents.urls")),
    path("api/v1/module-guides/", include("documents.module_guide_urls")),
    path("api/thongsothuyvan/", include(("thongsothuyvan.urls", "thongsothuyvan"), namespace="legacy-thongsothuyvan")),
    path("api/v1/thongsothuyvan/", include(("thongsothuyvan.urls", "thongsothuyvan"), namespace="v1-thongsothuyvan")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
