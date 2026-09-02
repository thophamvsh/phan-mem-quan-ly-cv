from rest_framework.routers import DefaultRouter

from .views import BoPhanViewSet, DonViToChucViewSet, NhaMayViewSet, NhanSuViewSet


router = DefaultRouter()
router.register("nha-may", NhaMayViewSet, basename="nha-may")
router.register("don-vi", DonViToChucViewSet, basename="don-vi")
router.register("bo-phan", BoPhanViewSet, basename="bo-phan")
router.register("nhan-su", NhanSuViewSet, basename="nhan-su")

urlpatterns = router.urls
