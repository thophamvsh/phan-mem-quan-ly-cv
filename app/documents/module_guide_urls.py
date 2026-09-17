from django.urls import path

from documents.views import (
    ModuleGuideContentAPIView,
    ModuleGuideCreateNextVersionAPIView,
    ModuleGuideDetailAPIView,
    ModuleGuideHistoryAPIView,
    ModuleGuideListCreateAPIView,
    ModuleGuidePublishAPIView,
    ModuleGuideRetireAPIView,
)


urlpatterns = [
    path("", ModuleGuideListCreateAPIView.as_view(), name="module-guide-list"),
    path("history/", ModuleGuideHistoryAPIView.as_view(), name="module-guide-history"),
    path("<int:pk>/", ModuleGuideDetailAPIView.as_view(), name="module-guide-detail"),
    path("<int:pk>/content/", ModuleGuideContentAPIView.as_view(), name="module-guide-content"),
    path("<int:pk>/publish/", ModuleGuidePublishAPIView.as_view(), name="module-guide-publish"),
    path("<int:pk>/retire/", ModuleGuideRetireAPIView.as_view(), name="module-guide-retire"),
    path(
        "<int:pk>/create-next-version/",
        ModuleGuideCreateNextVersionAPIView.as_view(),
        name="module-guide-create-next",
    ),
]
