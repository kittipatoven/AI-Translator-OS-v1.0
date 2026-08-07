import os
import shutil
import subprocess
from pathlib import Path


def cpu_percent():
    try:
        return float(open("/proc/stat").readline().split()[1])
    except Exception:
        return 0.0


def ram_usage():
    try:
        total, used, free = map(int, os.popen("free -m").readlines()[1].split()[1:4])
        return {"total": total, "used": used, "free": free}
    except Exception:
        return {"total": 0, "used": 0, "free": 0}


def temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return 0.0


def disk_usage(path="/"):
    try:
        return shutil.disk_usage(path)
    except Exception:
        return None


def run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return -1, "", str(exc)
