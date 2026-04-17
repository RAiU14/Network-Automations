from rest_framework import serializers
from .models import Device, Metric, AuditLog, ReportTask

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

class MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'

class ReportTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTask
        fields = '__all__'
