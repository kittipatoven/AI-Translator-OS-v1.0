# AI Translator OS v1.0 — Project Specification (SRS)

## 1. Objective

Develop a complete offline AI translator for Raspberry Pi 3.

- 100% offline after installation.
- No external API or cloud services.
- No API keys.
- Auto-start on boot.
- Modular, maintainable, Docker-based.

## 2. Hardware

- Raspberry Pi 3 (Raspberry Pi OS Lite 64-bit)
- LCD1602 I2C
- 5 push buttons (internal pull-up)
- USB microphone
- USB speaker
- microSD

| LCD1602 | Raspberry Pi |
|---------|--------------|
| GND     | Pin 6        |
| VCC     | Pin 2        |
| SDA     | GPIO2        |
| SCL     | GPIO3        |

| Button | GPIO |
|--------|------|
| LEFT   | 17   |
| RIGHT  | 27   |
| SPEAK  | 22   |
| REPLAY | 23   |
| MENU   | 24   |

## 3. Software Stack

- Python 3.11
- Docker / Docker Compose
- Whisper.cpp (speech-to-text)
- NLLB-200 Quantized (translation)
- Piper TTS (text-to-speech)

## 4. Functional Requirements

- Boot automatically
- Detect all hardware
- Detect missing or damaged models
- Auto-load configuration
- Display status on LCD
- Translate speech offline
- Speak translated result
- Store translation history
- Restart failed modules without rebooting the system
- Log every error and performance event

## 5. AI Pipeline

```
Microphone → Noise Reduction → VAD →
Whisper.cpp → Custom Dictionary →
Translation Rule Engine → NLLB-200 →
Back Translation → Confidence Score →
Piper TTS → Speaker
```

## 6. Modules

- `BootManager` — initialize and run diagnostics
- `LCDManager` — LCD1602 display
- `ButtonManager` — GPIO button handling
- `AudioManager` — recording and playback
- `SpeechManager` — Whisper.cpp integration
- `TranslationManager` — NLLB-200 integration
- `TTSManager` — Piper integration
- `ConversationManager` — continuous conversation
- `DictionaryManager` — custom technical dictionary
- `RuleEngine` — do-not-translate rules
- `BackTranslationManager` — quality verification
- `ConfidenceManager` — confidence scoring
- `HistoryManager` — translation history
- `LanguagePackManager` — language pack management
- `ModelManager` — model integrity checks
- `ResourceManager` — CPU/RAM/storage monitoring
- `WatchdogManager` — module health monitoring
- `DiagnosticsManager` — run self-tests
- `LoggingManager` — structured logging
- `ConfigManager` — JSON configuration
- `BackupManager` — offline backup
- `UpdateManager` — offline update from USB/microSD

## 7. Non-functional Requirements

- Fully offline
- Modular architecture
- Docker-based deployment
- Automatic recovery
- Automatic diagnostics
- Automatic startup
- Low memory usage
- Raspberry Pi 3 optimized
- Stable long-running operation
