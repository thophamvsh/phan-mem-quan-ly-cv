from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    SonghinhMnhViewSet,
    ThuongKonTumMnhViewSet,
    Vinhson_HoAViewSet,
    Vinhson_HoBViewSet,
    Vinhson_HocViewSet,
)

app_name = "thongsothuyvan"

router = DefaultRouter()
router.register(r"songhinh-mnh", SonghinhMnhViewSet, basename="songhinh-mnh")
router.register(r"thuongkontum-mnh", ThuongKonTumMnhViewSet, basename="thuongkontum-mnh")
router.register(r"vinhson-hoa", Vinhson_HoAViewSet, basename="vinhson-hoa")
router.register(r"vinhson-hob", Vinhson_HoBViewSet, basename="vinhson-hob")
router.register(r"vinhson-hoc", Vinhson_HocViewSet, basename="vinhson-hoc")

urlpatterns = [
    path("", include(router.urls)),
]