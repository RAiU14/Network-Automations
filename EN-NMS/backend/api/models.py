from django.db import models

class Device(models.Model):
    name = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(unique=True)
    snmp_community = models.CharField(max_length=255, default='public')
    snmp_version = models.IntegerField(default=2)
    is_active = models.BooleanField(default=True)
    
    # Metadata for AI/Lifecycle
    vendor = models.CharField(max_length=100, blank=True, null=True)
    model_number = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True)
    
    # Lifecycle dates (HW)
    eol_hw_date = models.DateField(blank=True, null=True)
    eos_hw_date = models.DateField(blank=True, null=True)
    
    last_polled_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.ip})"

class Telemetry(models.Model):
    """
    High-frequency metrics storage for AI training and historical analysis.
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='telemetry')
    metric_name = models.CharField(max_length=100) # e.g. cpu_util, mem_used, int_gi0_0_in
    value = models.FloatField()
    timestamp = models.DateTimeField(db_index=True) # Essential for time-series queries

    class Meta:
        verbose_name_plural = "Telemetry"
        ordering = ['-timestamp']

class AuditLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, related_name='logs')
    event_type = models.CharField(max_length=100) # e.g. POLL, CONFIG_CHANGE, ANSIBLE_RUN
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class AnsiblePlaybook(models.Model):
    """Tracking Ansible execution results."""
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    last_run_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, blank=True)
