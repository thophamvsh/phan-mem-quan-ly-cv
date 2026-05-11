from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    NhatKySuKienViewSet,
    SoBCHCSongHinhViewSet,
    SonhatkyvanhanhDieselViewSet,
    SonhatkyvanhanhViewSet,
    SogiaonhancaHCViewSet,
    SogiaonhancaVHViewSet,
)

app_name = "nhatkyvanhanh"

router = DefaultRouter()
router.register(r"nhat-ky-su-kien", NhatKySuKienViewSet, basename="nhatkysukien")
router.register(r"so-nhat-ky-van-hanh", SonhatkyvanhanhViewSet, basename="sonhatkyvanhanh")
router.register(r"so-nhat-ky-van-hanh-diesel", SonhatkyvanhanhDieselViewSet, basename="sonhatkyvanhanhdiesel")
router.register(r"so-bchc-song-hinh", SoBCHCSongHinhViewSet, basename="sobchcsonghinh")
router.register(r"so-giao-nhan-ca-vh", SogiaonhancaVHViewSet, basename="sogiaonhancavh")
router.register(r"so-giao-nhan-ca-hc", SogiaonhancaHCViewSet, basename="sogiaonhancahc")

urlpatterns = [
    path("", include(router.urls)),
]
