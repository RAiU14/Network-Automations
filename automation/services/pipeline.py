import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from automation.models import ReportTask, Device, PMMetric, AuditLog
from .ansible_service import AnsibleService

logger = logging.getLogger(__name__)

class ReportPipelineService:
    """
    Orchestrates the entire Preventive Maintenance workflow:
    1. Capture: Get live data from devices via Ansible.
    2. Extract: Parse captured logs using the optimized PM_Report pipeline.
    3. Persist: Save rich telemetry to PostgreSQL for future AI training.
    """
    _executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ReportWorker")

    def __init__(self):
        self.base_dir = Path(settings.BASE_DIR)
        self.upload_dir = self.base_dir / "Database" / "Uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.ansible = AnsibleService()

    def start_processing(self, task_id: int):
        self._executor.submit(self._execute_pipeline, task_id)

    def _execute_pipeline(self, task_id: int):
        try:
            task = ReportTask.objects.get(id=task_id)
            task.status = 'PROCESSING'
            task.save()

            log_dir = os.path.join(settings.BASE_DIR, 'logs', str(task_id))
            os.makedirs(log_dir, exist_ok=True)

            # --- STAGE 1: ANSIBLE CAPTURE ---
            logger.info(f"Task {task.ticket}: Starting Ansible Capture...")
            ansible_result = self.ansible.run_playbook(
                playbook_name='pm_capture.yml',
                extra_vars={'output_dir': log_dir}
            )

            # --- STAGE 2: EXTRACTION ---
            from PM_Report import pipeline
            logger.info(f"Task {task.ticket}: Parsing logs...")
            rows = pipeline.extract(log_dir, tech_hint=task.technology)

            # --- STAGE 3: PERSISTENCE (AI Data Mapping) ---
            self._save_pm_data(task, rows)

            task.status = 'COMPLETED'
            task.save()
            
            AuditLog.objects.create(
                event_type='LOG_ANALYSIS_COMPLETE',
                message=f"PM Report generated for {task.ticket}. {len(rows)} devices analyzed."
            )

        except Exception as e:
            logger.error(f"Pipeline error for task {task_id}: {e}")
            if 'task' in locals():
                task.status = 'FAILED'
                task.error_message = str(e)
                task.save()

    def _save_pm_data(self, task, rows):
        """
        Maps extracted PM report data to the PostgreSQL PMMetric model.
        """
        for row in rows:
            # Find or create device based on IP
            ip = row.get('Interface ip address')
            if not ip: continue

            device, _ = Device.objects.get_or_create(
                ip=ip, 
                defaults={'name': row.get('Host name', f'Device-{ip}')}
            )

            # Create PMMetric entry
            PMMetric.objects.create(
                device=device,
                ticket=task.ticket,
                cpu_utilization=self._to_float(row.get('CPU Utilization')),
                memory_utilization=self._to_float(row.get('Memory Utilization (%)')),
                fan_status=row.get('Fan status'),
                temp_status=row.get('Temperature status'),
                psu_status=row.get('PowerSupply status'),
                flash_used_pct=self._to_float(row.get('Used Flash (%)')),
                timestamp=timezone.now(),
                raw_data=row # Store everything for future AI parsing
            )

    @staticmethod
    def _to_float(value):
        try:
            if isinstance(value, (int, float)): return float(value)
            # Remove % signs or units if string
            if isinstance(value, str):
                cleaned = "".join(c for c in value if c.isdigit() or c == '.')
                return float(cleaned) if cleaned else 0.0
        except:
            return 0.0
        return 0.0
