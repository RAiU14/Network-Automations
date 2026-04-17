import os
import logging
import ansible_runner
from django.conf import settings

logger = logging.getLogger(__name__)

class AnsibleService:
    """
    Service to programmatically execute Ansible playbooks from the Django backend.
    """
    def __init__(self):
        self.project_dir = os.path.join(settings.BASE_DIR, '..', 'ansible')
        self.inventory_path = os.path.join(self.project_dir, 'inventory', 'hosts.yml')
        self.playbook_dir = os.path.join(self.project_dir, 'playbooks')

    def run_playbook(self, playbook_name, extra_vars=None, limit=None):
        """
        Executes a specific playbook using ansible-runner.
        """
        playbook_path = os.path.join(self.playbook_dir, playbook_name)
        
        if not os.path.exists(playbook_path):
            logger.error(f"Playbook not found: {playbook_path}")
            return None

        logger.info(f"Running Ansible Playbook: {playbook_name} (limit={limit})")

        # ansible-runner.run returns a Runner object
        r = ansible_runner.run(
            private_data_dir=self.project_dir,
            playbook=playbook_path,
            inventory=self.inventory_path,
            extravars=extra_vars or {},
            limit=limit or 'all',
            quiet=True # Suppress stdout flooding
        )

        logger.info(f"Ansible run finished. Status: {r.status}. RC: {r.rc}")
        
        # Return summary of results
        return {
            "status": r.status,
            "rc": r.rc,
            "stats": r.stats,
            "events": list(r.events) if r.rc != 0 else [] # Only return events on failure for brevity
        }

    def generate_inventory_from_db(self):
        """
        [Future Enhancement] Dynamically build Ansible inventory from Django Device model.
        """
        pass
