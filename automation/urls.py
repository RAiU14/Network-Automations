from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeviceViewSet, ReportTaskViewSet, EoxViewSet, AuditLogViewSet

router = DefaultRouter()
router.register(r'devices', DeviceViewSet)
router.register(r'reports', ReportTaskViewSet)
router.register(r'eox', EoxViewSet, basename='eox')
router.register(r'logs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
