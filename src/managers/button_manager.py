import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    from gpiozero import Button as _Button
except Exception as exc:
    _Button = None
    logger.debug("gpiozero not available: %s", exc)

try:
    import RPi.GPIO as _GPIO
except Exception as exc:
    _GPIO = None
    logger.debug("RPi.GPIO not available: %s", exc)


class ButtonManager:
    """GPIO button handling with gpiozero and a RPi.GPIO polling fallback.

    Works on the Raspberry Pi, inside Docker, and falls back to simulation on
    Windows/Linux/macOS.
    """

    def __init__(self, pin_config, short_ms=200, long_ms=800):
        self.pin_config = pin_config
        self.short_ms = short_ms
        self.long_ms = long_ms
        self._buttons = {}
        self._handlers = {
            name: {"short": None, "long": None, "press": None, "release": None}
            for name in pin_config
        }
        self._lock = threading.Lock()
        self._running = False
        self._threads = []

    def on(self, name, short=None, long=None, press=None, release=None):
        if short:
            self._handlers[name]["short"] = short
        if long:
            self._handlers[name]["long"] = long
        if press:
            self._handlers[name]["press"] = press
        if release:
            self._handlers[name]["release"] = release

    def start(self):
        if _Button is not None:
            for name, pin in self.pin_config.items():
                try:
                    btn = _Button(pin, pull_up=True, bounce_time=0.05)
                    btn.when_pressed = lambda n=name: self._handle_press(n)
                    btn.when_released = lambda n=name: self._handle_release(n)
                    self._buttons[name] = {
                        "button": btn,
                        "pressed_at": None,
                    }
                    logger.info("Button %s (GPIO%s) registered via gpiozero.", name, pin)
                except Exception as exc:
                    logger.warning(
                        "Button %s (GPIO%s) gpiozero failed (%s); falling back to polling.",
                        name, pin, exc,
                    )
                    self._start_polling(name, pin)
        elif _GPIO is not None:
            for name, pin in self.pin_config.items():
                self._start_polling(name, pin)
        else:
            logger.info("ButtonManager running in simulation mode (no GPIO).")

    def _start_polling(self, name, pin):
        try:
            _GPIO.setmode(_GPIO.BCM)
            _GPIO.setup(pin, _GPIO.IN, pull_up_down=_GPIO.PUD_UP)
            self._running = True
            t = threading.Thread(target=self._poll_loop, args=(name, pin), daemon=True)
            t.start()
            self._threads.append(t)
            logger.info("Button %s (GPIO%s) registered via RPi.GPIO polling.", name, pin)
        except Exception as exc:
            logger.error("Button %s (GPIO%s) polling setup failed: %s", name, pin, exc)

    def _poll_loop(self, name, pin):
        pressed_at = None
        while self._running:
            try:
                if _GPIO.input(pin) == 0 and pressed_at is None:
                    pressed_at = time.time()
                    self._handle_press(name)
                    press_handler = self._handlers[name].get("press")
                    if press_handler:
                        self._run_handler(press_handler, name)
                elif _GPIO.input(pin) == 1 and pressed_at is not None:
                    pressed_at = None
                    self._handle_release(name)
                    release_handler = self._handlers[name].get("release")
                    if release_handler:
                        self._run_handler(release_handler, name)
            except Exception as exc:
                logger.error("Button %s (GPIO%s) poll error: %s", name, pin, exc)
                break
            time.sleep(0.02)

    def _handle_press(self, name):
        with self._lock:
            if name in self._buttons:
                self._buttons[name]["pressed_at"] = time.time()

    def _handle_release(self, name):
        with self._lock:
            info = self._buttons.get(name)
            if not info or info.get("pressed_at") is None:
                return
            elapsed_ms = (time.time() - info["pressed_at"]) * 1000
            info["pressed_at"] = None
        handler = None
        if elapsed_ms >= self.long_ms:
            handler = self._handlers[name].get("long")
        elif elapsed_ms >= self.short_ms:
            handler = self._handlers[name].get("short")
        if handler:
            self._run_handler(handler, name)

    def _run_handler(self, handler, name):
        try:
            handler()
        except Exception as exc:
            logger.error("Button %s handler error: %s", name, exc)

    def simulate(self, name: str, duration_ms: float = 250.0) -> None:
        """Simulate a short press for the named button (useful for testing)."""
        if name not in self._handlers:
            logger.warning("Unknown button: %s", name)
            return
        if duration_ms < self.short_ms:
            duration_ms = self.short_ms
        with self._lock:
            self._buttons[name] = {"pressed_at": time.time() - (duration_ms / 1000.0)}
        self._handle_release(name)

    def stop(self):
        self._running = False
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
