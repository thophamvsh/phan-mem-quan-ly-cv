from django.urls import path
from rest_framework.routers import SimpleRouter
from .user_management_views import ManagedUserViewSet, ManagementOptionsAPIView

router = SimpleRouter()
router.register('users', ManagedUserViewSet, basename='managed-user')
urlpatterns = router.urls + [
    path('metadata/', ManagementOptionsAPIView.as_view()),
    path('assignable-roles/', ManagementOptionsAPIView.as_view(option='roles')),
    path('personnel-options/', ManagementOptionsAPIView.as_view(option='personnel')),
]
