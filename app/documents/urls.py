from django.urls import include, path
from rest_framework.routers import DefaultRouter

from documents.views import (
    DocumentDetailAPIView,
    DocumentListCreateAPIView,
    DocumentReprocessAPIView,
    DocumentSearchAPIView,
    DocumentViewAPIView,
    DocumentFolderViewSet,
)

router = DefaultRouter()
router.register("folders", DocumentFolderViewSet, basename="document-folders")

urlpatterns = [
    path("", DocumentListCreateAPIView.as_view(), name="documents-list"),
    path("search/", DocumentSearchAPIView.as_view(), name="documents-search"),
    path("<int:pk>/", DocumentDetailAPIView.as_view(), name="documents-detail"),
    path("<int:pk>/reprocess/", DocumentReprocessAPIView.as_view(), name="documents-reprocess"),
    path("<int:pk>/view/", DocumentViewAPIView.as_view(), name="documents-view"),
    path("", include(router.urls)),
]
