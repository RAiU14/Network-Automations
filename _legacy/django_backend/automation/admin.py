from django.contrib import admin
from .models import Device, Metric, AuditLog, ReportTask

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip', 'snmp_community', 'is_active', 'created_at')
    search_fields = ('name', 'ip')
    list_filter = ('is_active', 'created_at')

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('device', 'metric_name', 'value', 'polled_at')
    list_filter = ('device', 'metric_name', 'polled_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'message', 'timestamp')
    list_filter = ('event_type', 'timestamp')

@admin.register(ReportTask)
class ReportTaskAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'technology', 'status', 'created_at')
    list_filter = ('status', 'technology')
    search_fields = ('ticket',)
