"""In-process and external watchdog for AI Translator OS.

Monitors health checks every *interval* seconds. If a check fails more than
*max_failures* consecutive times, an optional restart callback is invoked and
the internal shutdown event is set, allowing Docker / systemd to restart the
container.

The watchdog can also probe the external REST /api/health endpoint every 30 s
and, if the whole container is unhealthy, attempt to restart it via the host's
docker/systemctl commands. As a last resort it can try to reboot the host.
"""

import logging
import shutil
import subprocess
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)


class WatchdogManager:
    """Simple in-process watchdog with optional container/host recovery."""

    def __init__(self, interval=30.0, max_failures=3, app_dir="/opt/translator"):
        self.interval = interval
        self._default_max_failures = max_failures
        self._app_dir = app_dir
        self._monitors = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._consecutive_unhealthy = 0

    def add(self, name, check_fn, restart_fn=None, max_failures=None):
        """Add a named health check."""
        with self._lock:
            self._monitors[name] = {
                "check": check_fn,
                "restart": restart_fn,
                "healthy": True,
                "failures": 0,
                "max_failures": max_failures if max_failures is not None else self._default_max_failures,
            }

    def is_shutdown(self):
        """Return True if the system should shut down."""
        return self._shutdown.is_set()

    def start(self):
        """Start the watchdog thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the watchdog thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 1)

    def _api_health(self):
        """Check the internal /api/health endpoint."""
        try:
            with urllib.request.urlopen(
                "http://localhost:8080/api/health", timeout=10
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _container_healthy(self):
        """Check if the translator container is marked healthy by docker."""
        if not shutil.which("docker"):
            return True
        try:
            out = subprocess.check_output(
                ["docker", "ps", "--filter", "name=translator", "--format", "{{.Names}} {{.Status}}"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            if not out.strip():
                return False
            # Status line looks like "translator Up 5 minutes (healthy)"
            return "(healthy)" in out or "(unhealthy)" not in out
        except Exception as exc:
            logger.warning("Docker container check failed: %s", exc)
            return True

    def _restart_container(self):
        """Attempt to restart the translator container via docker compose."""
        if not shutil.which("docker"):
            return False
        try:
            logger.warning("Restarting translator container...")
            subprocess.run(
                ["docker", "compose", "-f", f"{self._app_dir}/docker-compose.yml", "restart"],
                check=True,
                timeout=120,
            )
            return True
        except Exception as exc:
            logger.error("Container restart failed: %s", exc)
            return False

    def _restart_service(self):
        """Attempt to restart the systemd service."""
        if not shutil.which("systemctl"):
            return False
        try:
            logger.warning("Restarting translator-os systemd service...")
            subprocess.run(
                ["systemctl", "restart", "translator-os"],
                check=True,
                timeout=120,
            )
            return True
        except Exception as exc:
            logger.error("Systemd service restart failed: %s", exc)
            return False

    def _reboot_host(self):
        """As a last resort, try to reboot the host."""
        if not shutil.which("reboot"):
            return False
        try:
            logger.critical("Critical health failure. Rebooting host in 5 seconds...")
            time.sleep(5)
            subprocess.run(["reboot"], check=True, timeout=60)
            return True
        except Exception as exc:
            logger.error("Host reboot failed: %s", exc)
            return False

    def _escalate(self):
        """Try container, then service, then host reboot."""
        if self._restart_container():
            self._consecutive_unhealthy = 0
            return
        if self._restart_service():
            self._consecutive_unhealthy = 0
            return
        if self._consecutive_unhealthy >= 3:
            self._reboot_host()

    def _loop(self):
        while self._running and not self._shutdown.is_set():
            # Internal monitors
            with self._lock:
                for name, monitor in list(self._monitors.items()):
                    try:
                        if not monitor["check"]():
                            monitor["failures"] += 1
                            monitor["healthy"] = False
                            logger.warning(
                                "Watchdog check '%s' failed (%s/%s)",
                                name,
                                monitor["failures"],
                                monitor["max_failures"],
                            )
                            if monitor["failures"] >= monitor["max_failures"]:
                                logger.error(
                                    "Watchdog: '%s' exceeded max failures. Triggering restart.",
                                    name,
                                )
                                if monitor["restart"]:
                                    try:
                                        monitor["restart"]()
                                    except Exception as exc:
                                        logger.error("Watchdog restart for '%s' failed: %s", name, exc)
                                self._shutdown.set()
                        else:
                            if monitor["failures"] > 0:
                                logger.info("Watchdog check '%s' recovered", name)
                            monitor["failures"] = 0
                            monitor["healthy"] = True
                    except Exception as exc:
                        logger.error("Watchdog check '%s' threw: %s", name, exc)
                        monitor["failures"] += 1

            # External health and container checks
            try:
                if not self._api_health():
                    self._consecutive_unhealthy += 1
                    logger.warning("API /api/health not OK (%s/3)", self._consecutive_unhealthy)
                else:
                    if self._consecutive_unhealthy > 0:
                        logger.info("API /api/health recovered")
                    self._consecutive_unhealthy = 0

                if not self._container_healthy():
                    self._consecutive_unhealthy += 1
                    logger.warning("Container appears unhealthy")

                if self._consecutive_unhealthy >= 3:
                    self._escalate()
            except Exception as exc:
                logger.error("External health check error: %s", exc)

            time.sleep(self.interval)
