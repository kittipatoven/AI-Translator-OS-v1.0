#!/usr/bin/env python3
"""Host-side status display for AI Translator OS.

Run from the Raspberry Pi (not inside the container) with:
    python3 /opt/translator/scripts/status.py
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd, timeout=10, shell=False):
    try:
        return subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def check_os():
    cpuinfo = _run(["cat", "/proc/cpuinfo"], timeout=2)
    if "Raspberry Pi" in cpuinfo.stdout:
        return True, "Raspberry Pi OS"
    os_rel = Path("/etc/os-release")
    if os_rel.exists():
        text = os_rel.read_text(errors="ignore")
        m = re.search(r'PRETTY_NAME="([^"]+)"', text)
        if m:
            return True, m.group(1)
    return True, os.uname().sysname


def check_arch():
    return True, os.uname().machine


def check_docker():
    rc = _run(["systemctl", "is-active", "--quiet", "docker"], timeout=5).returncode
    return rc == 0, ("OK" if rc == 0 else "not running")


def check_container(app_dir):
    compose_file = Path(app_dir) / "docker-compose.yml"
    if not compose_file.exists():
        return False, "not installed"
    rc = _run(
        ["docker", "compose", "-f", str(compose_file), "ps"],
        timeout=15,
    )
    if rc.returncode != 0:
        return False, rc.stderr.strip().splitlines()[-1] if rc.stderr else "docker error"
    for line in rc.stdout.splitlines():
        if "translator" in line.lower() and "up" in line.lower():
            if "healthy" in line.lower() or "(" in line:
                return True, "RUNNING"
            return True, "UP"
    return False, "not running"


def _model_status(app_dir, name):
    d = Path(app_dir) / "models" / name
    if not d.is_dir():
        return False, "missing"
    files = [f for f in d.iterdir() if f.is_file() and f.name != ".gitkeep"]
    return bool(files), (f"{len(files)} files" if files else "empty")


def check_whisper(app_dir):
    return _model_status(app_dir, "whisper")


def check_nllb(app_dir):
    return _model_status(app_dir, "nllb")


def check_piper(app_dir):
    return _model_status(app_dir, "piper")


def check_lcd():
    if not shutil.which("i2cdetect"):
        return None, "i2cdetect not installed"
    rc = _run(["i2cdetect", "-y", "1"], timeout=5)
    if rc.returncode != 0:
        return False, "I2C error"
    addrs = ["0x27", "0x3f", "0x3F", "27", "3f", "3F"]
    if any(f" {a} " in rc.stdout or f"\n{a} " in rc.stdout or a in rc.stdout for a in addrs):
        return True, "0x27 / 0x3F"
    return False, "not detected"


def check_microphone():
    if not shutil.which("arecord"):
        return None, "arecord missing"
    rc = _run(["arecord", "-l"], timeout=5)
    if rc.returncode != 0 or "card" not in rc.stdout:
        return False, "not found"
    cards = [line for line in rc.stdout.splitlines() if "card" in line]
    return True, f"{len(cards)} card(s)"


def check_speaker():
    if not shutil.which("aplay"):
        return None, "aplay missing"
    rc = _run(["aplay", "-l"], timeout=5)
    if rc.returncode != 0 or "card" not in rc.stdout:
        return False, "not found"
    cards = [line for line in rc.stdout.splitlines() if "card" in line]
    return True, f"{len(cards)} card(s)"


def check_storage():
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        total_gb = total / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        label = f"{free_gb:.1f}G / {total_gb:.1f}G"
        if free_gb < 5:
            return False, label
        if free_gb < 10:
            return True, f"{label} (low)"
        return True, label
    except Exception as exc:
        return False, str(exc)


def check_ram():
    try:
        with open("/proc/meminfo") as f:
            data = f.read()
        total = int(re.search(r"MemTotal:\s+(\d+)", data).group(1)) / 1024
        avail = int(re.search(r"MemAvailable:\s+(\d+)", data).group(1)) / 1024
        return True, f"{avail:.0f}MB / {total:.0f}MB"
    except Exception as exc:
        return False, str(exc)


def check_swap():
    try:
        with open("/proc/meminfo") as f:
            data = f.read()
        total = int(re.search(r"SwapTotal:\s+(\d+)", data).group(1)) / 1024
        free = int(re.search(r"SwapFree:\s+(\d+)", data).group(1)) / 1024
        return True, f"{free:.0f}MB / {total:.0f}MB"
    except Exception as exc:
        return False, str(exc)


def check_temperature():
    if not shutil.which("vcgencmd"):
        return None, "vcgencmd missing"
    rc = _run(["vcgencmd", "measure_temp"], timeout=5)
    if rc.returncode != 0:
        return None, "unknown"
    val = rc.stdout.replace("temp=", "").strip()
    try:
        c = float(val.replace("'C", ""))
        if c > 80:
            return True, f"{val} (high)"
        return True, val
    except Exception:
        return True, val


def check_undervoltage():
    if not shutil.which("dmesg"):
        return None, "dmesg missing"
    rc = _run(["dmesg"], timeout=5)
    if rc.returncode != 0:
        return None, "dmesg error"
    lines = [l for l in rc.stdout.splitlines() if "undervoltage" in l.lower()]
    if not lines:
        return True, "NO"
    return False, "YES"


def check_service():
    rc = _run(["systemctl", "is-active", "--quiet", "translator-os"], timeout=5).returncode
    return rc == 0, ("active" if rc == 0 else "inactive")


def main():
    parser = argparse.ArgumentParser(description="AI Translator OS status")
    parser.add_argument("--app-dir", default="/opt/translator", help="Installation path")
    args = parser.parse_args()

    app_dir = args.app_dir

    results = [
        ("OS", *check_os()),
        ("Architecture", *check_arch()),
        ("Docker", *check_docker()),
        ("Container", *check_container(app_dir)),
        ("Whisper model", *check_whisper(app_dir)),
        ("NLLB model", *check_nllb(app_dir)),
        ("Piper model", *check_piper(app_dir)),
        ("LCD", *check_lcd()),
        ("Microphone", *check_microphone()),
        ("Speaker", *check_speaker()),
        ("Storage", *check_storage()),
        ("RAM", *check_ram()),
        ("Swap", *check_swap()),
        ("Temperature", *check_temperature()),
        ("Undervoltage", *check_undervoltage()),
        ("systemd service", *check_service()),
    ]

    print("AI TRANSLATOR STATUS")
    print("-" * 30)
    for label, ok, value in results:
        if ok is True:
            tag = "OK"
        elif ok is None:
            tag = "N/A"
        else:
            tag = "FAIL"
        print(f"{label:18s} {tag:5s} {value}")

    print("-" * 30)
    fails = [r for r in results if r[1] is False]
    unknowns = [r for r in results if r[1] is None]
    if fails:
        print("Overall Status: FAIL")
        return 1
    if unknowns:
        print("Overall Status: WARN")
        return 0
    print("Overall Status: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
