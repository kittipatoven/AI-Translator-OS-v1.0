import os
import sys
import time

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


def main():
    config = ConfigManager()
    log_mgr = LoggingManager(config)
    log_mgr.setup()

    boot = BootManager(config)
    boot.initialize()

    lcd = LCDManager(
        bus=config.get("lcd.i2c_bus", 1),
        address=config.get("lcd.i2c_address", 0x27),
    )
    lcd.display("AI Translator", "Booting...")

    audio = AudioManager(config)
    speech = SpeechManager(config.get("models.whisper_dir"))
    translation = TranslationManager(config.get("models.nllb_dir"))
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

    buttons = ButtonManager(config.get("buttons"))
    buttons.on("speak", short=conv.start_listening)
    buttons.on("replay", short=conv.replay)
    buttons.on("menu", short=conv.toggle_menu)
    buttons.on("left", short=conv.previous_language)
    buttons.on("right", short=conv.next_language)
    buttons.start()

    watchdog = WatchdogManager()
    watchdog.add("main", check_fn=lambda: True, restart_fn=lambda: None)
    watchdog.start()

    lcd.display("Ready", conv.source_name)
    try:
        while True:
            conv.idle()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        watchdog.stop()
        lcd.display("Shutting down", "")


if __name__ == "__main__":
    main()
