"""AI Translator OS v1.0 main entry point.

This module is intentionally defensive: any hardware or model that cannot be
initialised is logged as a warning and the web UI keeps running so the device
remains controllable.
"""

import logging
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from managers.config_manager import ConfigManager
from managers.lcd_manager import LCDManager
from managers.button_manager import ButtonManager
from managers.audio_manager import AudioManager
from managers.speech_manager import SpeechManager
from managers.translation_manager import TranslationManager
from managers.tts_manager import TTSManager
from managers.dictionary_manager import DictionaryManager
from managers.rule_engine import RuleEngine
from managers.back_translation_manager import BackTranslationManager
from managers.confidence_manager import ConfidenceManager
from managers.history_manager import HistoryManager
from managers.language_pack_manager import LanguagePackManager
from managers.resource_manager import ResourceManager
from managers.logging_manager import LoggingManager
from managers.watchdog_manager import WatchdogManager
from managers.conversation_manager import ConversationManager
from managers.boot_manager import BootManager
from web_server import WebServer


logger = logging.getLogger(__name__)


def _total_ram_mb():
    """Return total RAM in MB."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:
        return 0
    return 0


class _NoopTranslator:
    """Translation passthrough used when NLLB cannot be loaded."""

    def is_model_present(self) -> bool:
        return False

    def translate(self, text, source_lang, target_lang):
        return text


class _NoopTTS:
    """TTS stub used when Piper cannot be loaded."""

    def __init__(self):
        self._voice = None

    def is_model_present(self) -> bool:
        return False

    def set_voice(self, voice):
        self._voice = voice

    def set_language(self, lang):
        pass

    def speak(self, text, voice=None):
        raise RuntimeError("TTS not available")

    def replay(self):
        return None


class _NoopLCD:
    """LCD stub used when the LCD1602 is not connected."""

    def display(self, line1="", line2=""):
        print(f"[LCD] {line1} | {line2}")

    def clear(self):
        pass


def _safe_lcd(config):
    try:
        return LCDManager(
            bus=config.get("lcd.i2c_bus", 1),
            address=config.get("lcd.i2c_address", 0x27),
        )
    except Exception as exc:
        logger.warning("LCD not available, using console fallback: %s", exc)
        return _NoopLCD()


def _safe_audio(config):
    try:
        return AudioManager(config)
    except Exception as exc:
        logger.warning("AudioManager init failed: %s", exc)
        return AudioManager(config)  # already defensive; should not raise


def _safe_speech(config):
    try:
        return SpeechManager(config.get("models.whisper_dir"))
    except Exception as exc:
        logger.warning("SpeechManager init failed: %s", exc)
        return SpeechManager(config.get("models.whisper_dir"))


def _safe_translation(config):
    total_ram_mb = _total_ram_mb()
    nllb_dir = config.get("models.nllb_dir")
    if total_ram_mb > 0 and total_ram_mb < 1536:
        logger.warning("Low RAM (%s MB). NLLB disabled; using passthrough.", total_ram_mb)
        return _NoopTranslator()
    try:
        tm = TranslationManager(nllb_dir)
        if not tm.is_model_present():
            logger.warning("NLLB model not found at %s", nllb_dir)
            return _NoopTranslator()
        return tm
    except Exception as exc:
        logger.warning("NLLB TranslationManager failed: %s", exc)
        return _NoopTranslator()


def _safe_tts(config):
    try:
        tm = TTSManager(config.get("models.piper_dir"))
        if not tm.is_model_present():
            logger.warning("Piper voice not found at %s", config.get("models.piper_dir"))
            return _NoopTTS()
        return tm
    except Exception as exc:
        logger.warning("TTSManager failed: %s", exc)
        return _NoopTTS()


def _api_ok():
    try:
        with urllib.request.urlopen(
            "http://localhost:8080/api/health", timeout=5
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ram_ok():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    kb = int(line.split()[1])
                    return kb > 50 * 1024
    except Exception:
        return False
    return False


def main():
    """Start the translator with graceful hardware fallbacks."""
    config = ConfigManager()
    log_mgr = LoggingManager(config)
    log_mgr.setup()
    logger.info("AI Translator OS booting...")

    lcd = _safe_lcd(config)

    boot = BootManager(config, lcd)
    boot_ok = False
    try:
        boot_ok = boot.initialize()
    except Exception as exc:
        logger.warning("BootManager diagnostics failed: %s", exc)

    if not boot_ok:
        lcd.display("WARNING", "Hardware missing")
        logger.warning("Boot diagnostics detected missing hardware. Web UI active.")

    audio = _safe_audio(config)
    speech = _safe_speech(config)
    translation = _safe_translation(config)
    tts = _safe_tts(config)

    if isinstance(translation, _NoopTranslator):
        lcd.display("Translation", "Model missing")

    dictionary = DictionaryManager(config.get("dictionary_path"))
    rule = RuleEngine(list(dictionary.dictionary.keys()))
    back = BackTranslationManager(translator=translation)
    confidence = ConfidenceManager(config.get("confidence_threshold", 0.7))
    history = HistoryManager(config.get("history_path"))
    language_packs = LanguagePackManager("/app/data/language_packs")
    resource = ResourceManager(config)

    conv = ConversationManager(
        config=config,
        lcd=lcd,
        audio=audio,
        speech=speech,
        translation=translation,
        tts=tts,
        language_packs=language_packs,
        dictionary=dictionary,
        rule=rule,
        back=back,
        confidence=confidence,
        history=history,
        resource=resource,
    )

    watchdog = WatchdogManager(interval=30.0, max_failures=3, app_dir="/opt/translator")
    watchdog.add("health", _api_ok, restart_fn=lambda: logger.critical("API unresponsive; restarting"))
    watchdog.add("whisper", speech.is_model_present, max_failures=2)
    watchdog.add("nllb", translation.is_model_present, max_failures=2)
    watchdog.add("piper", tts.is_model_present, max_failures=2)
    watchdog.add("ram", _ram_ok, max_failures=1)
    watchdog.add("disk", resource.is_disk_critical, max_failures=1)
    watchdog.add("throttle", resource.is_throttled, max_failures=3)
    watchdog.start()

    web = WebServer(conv)
    web.start()
    logger.info("Web server started on %s:%s", web.host, web.port)

    try:
        buttons = ButtonManager(config.get("buttons"))
        buttons.on("speak", short=conv.start_listening)
        buttons.on("replay", short=conv.replay)
        buttons.on("menu", short=conv.toggle_menu)
        buttons.on("left", short=conv.previous_language)
        buttons.on("right", short=conv.next_language)
        buttons.start()
    except Exception as exc:
        logger.warning("ButtonManager unavailable, use web UI: %s", exc)

    if boot_ok:
        lcd.display("Ready", conv.source_name)
    else:
        lcd.display("Ready", "Web UI active")

    try:
        while not watchdog.is_shutdown():
            conv.idle()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        watchdog.stop()
        lcd.display("Shutting down", "")


if __name__ == "__main__":
    main()
