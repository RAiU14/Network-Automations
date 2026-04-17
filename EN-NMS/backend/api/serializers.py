from rest_framework import serializers
from .models import Device, Telemetry, AuditLog, AnsiblePlaybook

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'

class TelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Telemetry
        fields = ['metric_name', 'value', 'timestamp']

class AuditLogSerializer(serializers.ModelSerializer):
    device_name = serializers.ReadOnlyField(source='device.name')
    
    class Meta:
        model = AuditLog
        fields = ['id', 'device_name', 'event_type', 'message', 'timestamp']

class AnsiblePlaybookSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnsiblePlaybook
        fields = '__all__'
