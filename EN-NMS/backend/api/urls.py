from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeviceViewSet, AnalyticsViewSet, DashboardStatsViewSet, AuditLogViewSet

router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'logs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', AnalyticsViewSet.as_view({'get': 'list'}), name='analytics'),
    path('dashboard/stats/', DashboardStatsViewSet.as_view({'get': 'list'}), name='dashboard-stats'),
    path('health/', lambda r: Response({"status": "ok"}), name='health'), # placeholder
]
