from django.urls import path

from documents.views import (
    DocumentDetailAPIView,
    DocumentListCreateAPIView,
    DocumentReprocessAPIView,
    DocumentSearchAPIView,
    DocumentViewAPIView,
)


urlpatterns = [
    path("", DocumentListCreateAPIView.as_view(), name="documents-list"),
    path("search/", DocumentSearchAPIView.as_view(), name="documents-search"),
    path("<int:pk>/", DocumentDetailAPIView.as_view(), name="documents-detail"),
    path("<int:pk>/reprocess/", DocumentReprocessAPIView.as_view(), name="documents-reprocess"),
    path("<int:pk>/view/", DocumentViewAPIView.as_view(), name="documents-view"),
]
