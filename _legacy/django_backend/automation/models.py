from django.db import models

class Device(models.Model):
    name = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(unique=True)
    snmp_community = models.CharField(max_length=100, default='public')
    snmp_version = models.IntegerField(default=2)
    is_active = models.BooleanField(default=True)
    
    # Metadata for AI/Lifecycle Mapping
    vendor = models.CharField(max_length=100, blank=True, null=True, default="Cisco")
    model_number = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True)
    
    # Cisco Hardware Lifecycle Dates
    eol_hw_date = models.DateField(blank=True, null=True, help_text="End-of-Sale Date: HW")
    eos_hw_date = models.DateField(blank=True, null=True, help_text="Last Date of Support: HW")
    
    mac_address = models.CharField(max_length=100, blank=True, null=True)
    hardware_info = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.ip})"

class PMMetric(models.Model):
    """
    Specifically structured telemetry for Preventive Maintenance.
    Allows for AI-driven anomaly detection on specific hardware components.
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='pm_metrics')
    ticket = models.CharField(max_length=50, blank=True, null=True) # Linked to the PM report request
    
    # Core Health Indicators
    cpu_utilization = models.FloatField(null=True, blank=True)
    memory_utilization = models.FloatField(null=True, blank=True)
    fan_status = models.CharField(max_length=50, blank=True, null=True)
    temp_status = models.CharField(max_length=50, blank=True, null=True)
    psu_status = models.CharField(max_length=50, blank=True, null=True)
    
    # Flash storage
    flash_used_pct = models.FloatField(null=True, blank=True)
    
    timestamp = models.DateTimeField(db_index=True)
    raw_data = models.JSONField(blank=True, null=True) # For any extra fields

    class Meta:
        ordering = ['-timestamp']

class Metric(models.Model):
    """Legacy generic metrics table"""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='metrics')
    metric_name = models.CharField(max_length=100)
    value = models.TextField(blank=True, null=True)
    polled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} - {self.metric_name}: {self.value}"

class AuditLog(models.Model):
    event_type = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']

class ReportTask(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    ticket = models.CharField(max_length=50, unique=True)
    technology = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket {self.ticket} - {self.status}"
