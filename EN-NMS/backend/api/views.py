from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Device, Telemetry, AuditLog
from .serializers import DeviceSerializer, TelemetrySerializer, AuditLogSerializer
from django.db.models import Max, Count
from django.utils import timezone
from datetime import timedelta

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_with_ids = DeviceSerializer
    serializer_class = DeviceSerializer

    @action(detail=True, methods=['post'])
    def poll(self, request, pk=None):
        """Trigger a manual poll for a specific device."""
        device = self.get_object()
        # Placeholder for actual background task logic (e.g. Celery)
        # For now, we mock success
        AuditLog.objects.create(
            device=device,
            event_type='POLL',
            message=f"Manual poll triggered for {device.name}"
        )
        return Response({"status": "success", "message": f"Poll triggered for {device.name}"})

class AnalyticsViewSet(viewsets.ViewSet):
    def list(self, request):
        # 1. Bandwidth Peaks (Mock logic translated from existing SQLite queries)
        # In a real scenario, we would aggregate from Telemetry table
        peaks = Telemetry.objects.values('device__name').annotate(peak=Max('value')).order_by('-peak')[:5]
        
        # 2. Uptime Summary
        total = Device.objects.count()
        up = Device.objects.filter(is_active=True).count()
        
        # 3. Recent Activity
        recent_logs = AuditLog.objects.all()[:10]
        
        return Response({
            "bandwidth_peaks": peaks,
            "uptime_stats": {
                "up": up, 
                "total": total, 
                "percentage": (up/total*100) if total > 0 else 0
            },
            "recent_activity": AuditLogSerializer(recent_logs, many=True).data
        })

class DashboardStatsViewSet(viewsets.ViewSet):
    def list(self, request):
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        
        return Response({
            "total_devices": Device.objects.count(),
            "active_devices": Device.objects.filter(is_active=True).count(),
            "total_metrics_24h": Telemetry.objects.filter(timestamp__gte=yesterday).count(),
            "health_score": 98.5
        })

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
