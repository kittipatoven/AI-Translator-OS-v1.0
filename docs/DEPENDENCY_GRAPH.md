# AI Translator OS v1.0 — Dependency Graph
## Per-File Imports and Classes

### scripts/download_models.py
- Classes: -
- Imports:
  - `argparse`
  - `os`
  - `pathlib.Path`

### scripts/generate_dependency_graph.py
- Classes: -
- Imports:
  - `ast`
  - `json`
  - `pathlib.Path`

### src/main.py
- Classes: -
- Imports:
  - `managers.audio_manager.AudioManager`
  - `managers.back_translation_manager.BackTranslationManager`
  - `managers.boot_manager.BootManager`
  - `managers.button_manager.ButtonManager`
  - `managers.confidence_manager.ConfidenceManager`
  - `managers.config_manager.ConfigManager`
  - `managers.conversation_manager.ConversationManager`
  - `managers.dictionary_manager.DictionaryManager`
  - `managers.history_manager.HistoryManager`
  - `managers.language_pack_manager.LanguagePackManager`
  - `managers.lcd_manager.LCDManager`
  - `managers.logging_manager.LoggingManager`
  - `managers.resource_manager.ResourceManager`
  - `managers.rule_engine.RuleEngine`
  - `managers.speech_manager.SpeechManager`
  - `managers.translation_manager.TranslationManager`
  - `managers.tts_manager.TTSManager`
  - `managers.watchdog_manager.WatchdogManager`
  - `os`
  - `sys`
  - `time`

### src/managers/__init__.py
- Classes: -
- Imports:

### src/managers/audio_manager.py
- Classes: AudioManager
- Imports:
  - `os`
  - `pathlib.Path`
  - `subprocess`
  - `tempfile`
  - `time`
  - `wave`

### src/managers/back_translation_manager.py
- Classes: BackTranslationManager
- Imports:
  - `difflib.SequenceMatcher`

### src/managers/backup_manager.py
- Classes: BackupManager
- Imports:
  - `json`
  - `pathlib.Path`
  - `shutil`
  - `time`
  - `zipfile`

### src/managers/boot_manager.py
- Classes: BootManager
- Imports:
  - `managers.model_manager.ModelManager`
  - `os`
  - `pathlib.Path`
  - `time`
  - `utils.system_helper`

### src/managers/button_manager.py
- Classes: ButtonManager
- Imports:
  - `threading`
  - `time`

### src/managers/confidence_manager.py
- Classes: ConfidenceManager
- Imports:
  - `math`

### src/managers/config_manager.py
- Classes: ConfigManager
- Imports:
  - `json`
  - `os`
  - `pathlib.Path`

### src/managers/conversation_manager.py
- Classes: ConversationManager
- Imports:
  - `pathlib.Path`
  - `threading`
  - `time`

### src/managers/diagnostics_manager.py
- Classes: DiagnosticsManager
- Imports:
  - `pathlib.Path`
  - `utils.system_helper`

### src/managers/dictionary_manager.py
- Classes: DictionaryManager
- Imports:
  - `json`
  - `pathlib.Path`

### src/managers/history_manager.py
- Classes: HistoryManager
- Imports:
  - `json`
  - `pathlib.Path`
  - `time`

### src/managers/language_pack_manager.py
- Classes: LanguagePackManager
- Imports:
  - `json`
  - `pathlib.Path`

### src/managers/lcd_manager.py
- Classes: LCDManager
- Imports:
  - `pathlib.Path`
  - `time`
  - `utils.i2c_helper.I2CHelper`

### src/managers/logging_manager.py
- Classes: LoggingManager
- Imports:
  - `logging`
  - `logging.handlers.RotatingFileHandler`
  - `pathlib.Path`

### src/managers/model_manager.py
- Classes: ModelManager
- Imports:
  - `hashlib`
  - `json`
  - `pathlib.Path`

### src/managers/resource_manager.py
- Classes: ResourceManager
- Imports:
  - `os`
  - `pathlib.Path`
  - `shutil`
  - `time`
  - `utils.system_helper`

### src/managers/rule_engine.py
- Classes: RuleEngine
- Imports:
  - `re`

### src/managers/speech_manager.py
- Classes: SpeechManager
- Imports:
  - `os`
  - `pathlib.Path`
  - `subprocess`

### src/managers/translation_manager.py
- Classes: TranslationManager
- Imports:
  - `logging`
  - `pathlib.Path`
  - `typing.Optional`

### src/managers/tts_manager.py
- Classes: TTSManager
- Imports:
  - `pathlib.Path`
  - `shutil`
  - `subprocess`

### src/managers/update_manager.py
- Classes: UpdateManager
- Imports:
  - `json`
  - `pathlib.Path`
  - `shutil`
  - `subprocess`
  - `time`

### src/managers/watchdog_manager.py
- Classes: WatchdogManager
- Imports:
  - `threading`
  - `time`

### src/utils/__init__.py
- Classes: -
- Imports:

### src/utils/i2c_helper.py
- Classes: I2CHelper
- Imports:

### src/utils/system_helper.py
- Classes: -
- Imports:
  - `os`
  - `pathlib.Path`
  - `shutil`
  - `subprocess`

## Call Graph Summary

```
main.py
├── managers/config_manager.py
├── managers/lcd_manager.py
├── managers/button_manager.py
├── managers/audio_manager.py
├── managers/speech_manager.py
├── managers/translation_manager.py
├── managers/tts_manager.py
├── managers/conversation_manager.py
├── managers/dictionary_manager.py
├── managers/rule_engine.py
├── managers/back_translation_manager.py
├── managers/confidence_manager.py
├── managers/history_manager.py
├── managers/language_pack_manager.py
├── managers/resource_manager.py
├── managers/logging_manager.py
├── managers/watchdog_manager.py
└── utils/*
```
