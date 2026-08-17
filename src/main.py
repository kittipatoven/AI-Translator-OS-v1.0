import logging
import os
import sys
import time
import urllib.request

# Ensure the project root is importable when not using PYTHONPATH
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


def _total_ram_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:
        return 0
    return 0


class _NoopTranslator:
    """Translation passthrough used when there is not enough RAM to load NLLB."""

    def is_model_present(self) -> bool:
        return False

    def translate(self, text, source_lang, target_lang):
        return text


def main():
    config = ConfigManager()
    log_mgr = LoggingManager(config)
    log_mgr.setup()

    lcd = LCDManager(
        bus=config.get("lcd.i2c_bus", 1),
        address=config.get("lcd.i2c_address", 0x27),
    )

    boot = BootManager(config, lcd)
    boot_ok = boot.initialize()

    if not boot_ok:
        lcd.display("ERROR", "Check hardware")

    audio = AudioManager(config)
    speech = SpeechManager(config.get("models.whisper_dir"))

    total_ram_mb = _total_ram_mb()
    nllb_dir = config.get("models.nllb_dir")
    if total_ram_mb < 1536:
        logger.warning("Low RAM (%s MB). NLLB disabled; using passthrough.", total_ram_mb)
        translation = _NoopTranslator()
        lcd.display("LOW RAM", "NLLB off")
    else:
        translation = TranslationManager(nllb_dir)
        if not translation.is_model_present():
            lcd.display("ERROR", "Translation Model")
    tts = TTSManager(config.get("models.piper_dir"))
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

    def _api_ok():
        try:
            with urllib.request.urlopen(
                "http://localhost:8080/api/status", timeout=5
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
                        return kb > 50 * 1024  # at least 50 MB available
        except Exception:
            return False
        return False

    watchdog = WatchdogManager(interval=10.0, max_failures=3)
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

    buttons = ButtonManager(config.get("buttons"))
    buttons.on("speak", short=conv.start_listening)
    buttons.on("replay", short=conv.replay)
    buttons.on("menu", short=conv.toggle_menu)
    buttons.on("left", short=conv.previous_language)
    buttons.on("right", short=conv.next_language)
    try:
        buttons.start()
    except Exception as exc:
        print(f"[main] ButtonManager failed, continuing without GPIO: {exc}")

    if boot_ok:
        lcd.display("Ready", conv.source_name)
    else:
        lcd.display("ERROR", "Check hardware")
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
