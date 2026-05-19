"""Daily database backup script for Windows Task Scheduler.

Usage:
    python backup.py              # Run backup now
    python backup.py --install    # Create scheduled task (daily at 3am)
    python backup.py --uninstall  # Remove scheduled task
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from db import backup_db


def install_task():
    """Create a Windows Task Scheduler entry for daily backups at 3am."""
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup.py")
    python = sys.executable
    cmd = [
        "schtasks", "/create",
        "/tn", "RetroZone-DB-Backup",
        "/tr", f'"{python}" "{script}"',
        "/sc", "daily",
        "/st", "03:00",
        "/f"
    ]
    subprocess.run(cmd, check=True)
    print("Scheduled task 'RetroZone-DB-Backup' created (daily at 3:00 AM)")


def uninstall_task():
    """Remove the backup scheduled task."""
    import subprocess
    subprocess.run(["schtasks", "/delete", "/tn", "RetroZone-DB-Backup", "/f"], check=True)
    print("Scheduled task 'RetroZone-DB-Backup' removed")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_task()
    elif "--uninstall" in sys.argv:
        uninstall_task()
    else:
        backup_db()
