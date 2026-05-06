from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    SonghinhMnhViewSet,
    ThuongKonTumMnhViewSet,
    Vinhson_HoAViewSet,
    Vinhson_HoBViewSet,
    Vinhson_HocViewSet,
    ThongsoSanxuatViewSet,
    ThongsoGioPhatViewSet,
    DeletePlantDataByDateAPIView,
    HydrologyPlantsAPIView,
    ManualHydrologyDataAPIView,
)
from .sync_views import PreviewGoogleSheetAPIView, SaveGoogleSheetDataAPIView, PreviewGioPhatAPIView, SaveGioPhatAPIView

app_name = "thongsothuyvan"

router = DefaultRouter()
router.register(r"song-hinh-mnh", SonghinhMnhViewSet, basename="songhinh-mnh")
router.register(r"thuong-kon-tum-mnh", ThuongKonTumMnhViewSet, basename="thuongkontum-mnh")
router.register(r"vinhson-ho-a", Vinhson_HoAViewSet, basename="vinhson-hoa")
router.register(r"vinhson-ho-b", Vinhson_HoBViewSet, basename="vinhson-hob")
router.register(r"vinhson-ho-c", Vinhson_HocViewSet, basename="vinhson-hoc")
router.register(r"thongsosanxuat", ThongsoSanxuatViewSet, basename="thongsosanxuat")
router.register(r"thongsogiophat", ThongsoGioPhatViewSet, basename="thongsogiophat")

urlpatterns = [
    path("", include(router.urls)),
    path("plants/", HydrologyPlantsAPIView.as_view(), name="plants"),
    path("sync/preview/", PreviewGoogleSheetAPIView.as_view(), name="sync-preview"),
    path("sync/save/", SaveGoogleSheetDataAPIView.as_view(), name="sync-save"),
    path("sync/delete-date/", DeletePlantDataByDateAPIView.as_view(), name="sync-delete-date"),
    path("manual-entry/", ManualHydrologyDataAPIView.as_view(), name="manual-entry"),
    path("sync-giophat/preview/", PreviewGioPhatAPIView.as_view(), name="sync-giophat-preview"),
    path("sync-giophat/save/", SaveGioPhatAPIView.as_view(), name="sync-giophat-save"),
]
