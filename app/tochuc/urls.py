from rest_framework.routers import DefaultRouter

from .views import BoPhanViewSet, DonViToChucViewSet


router = DefaultRouter()
router.register("don-vi", DonViToChucViewSet, basename="don-vi")
router.register("bo-phan", BoPhanViewSet, basename="bo-phan")

urlpatterns = router.urls
