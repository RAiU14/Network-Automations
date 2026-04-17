import sys
from pathlib import Path
from django.conf import settings

# Add project root to path to reach Alive_Checks and Log_Capture
sys.path.append(str(Path(settings.BASE_DIR).parent))

import Alive_Checks
import Log_Capture

class NetworkToolService:
    @staticmethod
    def ping(ip: str):
        """Wrapper for Alive_Checks.alive_check"""
        return Alive_Checks.alive_check(ip)

    @staticmethod
    def capture_logs(ip: str, commands: list):
        """Wrapper for Log_Capture.exec_command"""
        # Note: In a production Django app, this should be backgrounded
        # For now, we maintain the direct call pattern
        return Log_Capture.exec_command(ip, commands)
