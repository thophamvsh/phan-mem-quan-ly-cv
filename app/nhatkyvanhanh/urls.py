from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NhatKySuKienViewSet, SogiaonhancaVHViewSet

app_name = "nhatkyvanhanh"

router = DefaultRouter()
router.register(r"nhat-ky-su-kien", NhatKySuKienViewSet, basename="nhatkysukien")
router.register(r"so-giao-nhan-ca-vh", SogiaonhancaVHViewSet, basename="sogiaonhancavh")

urlpatterns = [
    path("", include(router.urls)),
]

