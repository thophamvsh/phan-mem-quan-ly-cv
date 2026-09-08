from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .audit_views import (
    AuditExportExcelView,
    AuditMetadataView,
    DataChangeLogViewSet,
    DataSyncAuditViewSet,
    UserActivityLogViewSet,
    UserManagementAuditViewSet,
)

router = DefaultRouter()
router.register(r'activity-logs', UserActivityLogViewSet, basename='audit-activity-log')
router.register(r'data-changes', DataChangeLogViewSet, basename='audit-data-change')
router.register(r'data-syncs', DataSyncAuditViewSet, basename='audit-data-sync')
router.register(r'user-management', UserManagementAuditViewSet, basename='audit-user-management')

urlpatterns = [
    path('metadata/', AuditMetadataView.as_view(), name='audit-metadata'),
    path('export-excel/', AuditExportExcelView.as_view(), name='audit-export-excel'),
    path('', include(router.urls)),
]
