import logging
import threading
import time

logger = logging.getLogger(__name__)


class WatchdogManager:
    """Simple in-process watchdog.

    Monitors a set of health checks every *interval* seconds.  If a check
    fails more than *max_failures* consecutive times, an optional restart
    callback is invoked and the internal shutdown event is set.  The main
    loop can observe this event and exit cleanly, allowing Docker /
    systemd to restart the entire container.
    """

    def __init__(self, interval=5.0, max_failures=3):
        self.interval = interval
        self._default_max_failures = max_failures
        self._monitors = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._shutdown = threading.Event()

    def add(self, name, check_fn, restart_fn=None, max_failures=None):
        with self._lock:
            self._monitors[name] = {
                "check": check_fn,
                "restart": restart_fn,
                "healthy": True,
                "failures": 0,
                "max_failures": max_failures if max_failures is not None else self._default_max_failures,
            }

    def is_shutdown(self):
        return self._shutdown.is_set()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 1)

    def _loop(self):
        while self._running and not self._shutdown.is_set():
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
            time.sleep(self.interval)
