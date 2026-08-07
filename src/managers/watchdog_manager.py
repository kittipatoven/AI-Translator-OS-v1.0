import time
import threading


class WatchdogManager:
    def __init__(self, interval=5.0):
        self.interval = interval
        self._monitors = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def add(self, name, check_fn, restart_fn):
        with self._lock:
            self._monitors[name] = {"check": check_fn, "restart": restart_fn, "healthy": True}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 1)

    def _loop(self):
        while self._running:
            with self._lock:
                for name, monitor in self._monitors.items():
                    try:
                        if not monitor["check"]():
                            monitor["healthy"] = False
                            monitor["restart"]()
                    except Exception as exc:
                        print(f"[Watchdog] {name} error: {exc}")
            time.sleep(self.interval)
