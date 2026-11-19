"""Restart a resolver that stops answering, then confirm it answers again."""
import subprocess
import time


def heal(check, restart, retries=3, settle=2.0, sleep=time.sleep):
    """check() returns True when healthy. Returns healthy, restarted or failed."""
    for attempt in range(retries):
        if check():
            return "healthy" if attempt == 0 else "recovered"
        sleep(1.0)
    restart()
    sleep(settle)
    return "restarted" if check() else "failed"


def shell_restart(command):
    return lambda: subprocess.run(command, shell=True, check=True)
