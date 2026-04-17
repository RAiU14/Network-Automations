"""
Ansible orchestration service.
Uses lazy import of ansible_runner since it requires fcntl (Linux-only).
On Windows dev machines, playbook execution will log a warning instead of crashing.
"""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AnsibleService:
    """
    Service to programmatically execute Ansible playbooks from the Django backend.
    ansible-runner is imported lazily because it depends on fcntl (Linux-only).
    """

    def __init__(self):
        self.project_dir = os.path.join(settings.BASE_DIR, 'ansible')
        self.inventory_path = os.path.join(self.project_dir, 'inventory', 'hosts.yml')
        self.playbook_dir = os.path.join(self.project_dir, 'playbooks')

    def run_playbook(self, playbook_name, extra_vars=None, limit=None):
        """Executes a specific playbook using ansible-runner."""
        try:
            import ansible_runner
        except ImportError:
            logger.warning(
                "ansible-runner is not available on this platform (Windows). "
                "Playbook execution skipped. Deploy to Linux for full Ansible support."
            )
            return {"status": "skipped", "rc": -1, "reason": "ansible-runner unavailable (Windows)"}

        playbook_path = os.path.join(self.playbook_dir, playbook_name)

        if not os.path.exists(playbook_path):
            logger.error(f"Playbook not found: {playbook_path}")
            return None

        logger.info(f"Running Ansible Playbook: {playbook_name} (limit={limit})")

        r = ansible_runner.run(
            private_data_dir=self.project_dir,
            playbook=playbook_path,
            inventory=self.inventory_path,
            extravars=extra_vars or {},
            limit=limit or 'all',
            quiet=True,
        )

        logger.info(f"Ansible run finished. Status: {r.status}. RC: {r.rc}")
        return {
            "status": r.status,
            "rc": r.rc,
            "stats": r.stats,
            "events": list(r.events) if r.rc != 0 else [],
        }

    def generate_inventory_from_db(self):
        """[Future] Dynamically build Ansible inventory from Django Device model."""
        pass
