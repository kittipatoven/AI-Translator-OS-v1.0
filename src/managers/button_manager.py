import time
import threading

try:
    from gpiozero import Button
except Exception as exc:
    Button = None
    print(f"[ButtonManager] gpiozero not available: {exc}")


class ButtonManager:
    def __init__(self, pin_config, short_ms=200, long_ms=800):
        self.pin_config = pin_config
        self.short_ms = short_ms
        self.long_ms = long_ms
        self._buttons = {}
        self._handlers = {name: {"short": None, "long": None} for name in pin_config}
        self._lock = threading.Lock()

    def on(self, name, short=None, long=None):
        if short:
            self._handlers[name]["short"] = short
        if long:
            self._handlers[name]["long"] = long

    def start(self):
        if Button is None:
            print("[ButtonManager] Running in simulation mode (no GPIO).")
            return
        for name, pin in self.pin_config.items():
            try:
                btn = Button(pin, pull_up=True, bounce_time=0.05)
                btn.when_pressed = lambda n=name: self._handle_press(n)
                btn.when_released = lambda n=name: self._handle_release(n)
                self._buttons[name] = {
                    "button": btn,
                    "pressed_at": None,
                }
                print(f"[ButtonManager] {name} (GPIO{pin}) registered.")
            except Exception as exc:
                print(f"[ButtonManager] Could not register {name} (GPIO{pin}): {exc}")

    def _handle_press(self, name):
        with self._lock:
            if name in self._buttons:
                self._buttons[name]["pressed_at"] = time.time()

    def _handle_release(self, name):
        with self._lock:
            info = self._buttons.get(name)
            if not info or info["pressed_at"] is None:
                return
            elapsed_ms = (time.time() - info["pressed_at"]) * 1000
            info["pressed_at"] = None
        handler = None
        if elapsed_ms >= self.long_ms:
            handler = self._handlers[name].get("long")
        elif elapsed_ms >= self.short_ms:
            handler = self._handlers[name].get("short")
        if handler:
            try:
                handler()
            except Exception as exc:
                print(f"[ButtonManager] {name} handler error: {exc}")
