from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Device, Metric, AuditLog, ReportTask
from .serializers import DeviceSerializer, MetricSerializer, AuditLogSerializer, ReportTaskSerializer
from .services.eox import EoxScraperService
from .services.pipeline import ReportPipelineService
from .services.network import NetworkToolService

class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

    @action(detail=True, methods=['get'])
    def ping(self, request, pk=None):
        device = self.get_object()
        result = NetworkToolService.ping(device.ip)
        return Response({"ip": device.ip, "reachable": "Passed" in result, "raw": result})

class ReportTaskViewSet(viewsets.ModelViewSet):
    queryset = ReportTask.objects.all()
    serializer_class = ReportTaskSerializer

    def create(self, request, *args, **kwargs):
        # Override create to trigger the background pipeline
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        
        # Trigger pipeline
        pipeline = ReportPipelineService()
        pipeline.start_processing(task.id)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class EoxViewSet(viewsets.ViewSet):
    def list(self, request):
        categories = EoxScraperService.get_categories()
        return Response({"categories": categories})

    @action(detail=False, methods=['post'])
    def check(self, request):
        product_link = request.data.get('product_link')
        if not product_link:
            return Response({"error": "product_link required"}, status=400)
        announcement = EoxScraperService.check_eox_announcement(product_link)
        return Response({"announcement": announcement})

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
