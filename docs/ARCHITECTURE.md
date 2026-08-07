# AI Translator OS v1.0 — Architecture

## Directory Layout

```
AI Translator OS v1.0/
├── .windsurfrules          # Windsurf AI rules
├── README.md
├── config/
│   └── config.json         # runtime configuration
├── data/
│   ├── dictionary.json     # custom dictionary
│   ├── history.jsonl       # translation history
│   └── language_packs/     # language pack definitions
├── dictionary/             # extra dictionaries
├── docs/                   # documentation
├── docker/                 # Docker helper files
├── logs/                   # rotated logs
├── models/
│   ├── whisper/            # Whisper.cpp models
│   ├── nllb/               # NLLB-200 models
│   └── piper/              # Piper voices
├── scripts/
│   ├── download_models.py  # offline model downloader
│   └── translator-os.service # systemd unit
├── src/
│   ├── main.py             # entry point
│   ├── managers/           # high-level managers
│   ├── modules/            # reusable functional modules
│   └── utils/              # I2C and system helpers
├── tests/                  # unit and integration tests
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Data Flow

1. The user presses `SPEAK`.
2. `ButtonManager` notifies `ConversationManager`.
3. `AudioManager` records audio from the USB microphone.
4. `SpeechManager` (Whisper.cpp) transcribes the audio.
5. `DictionaryManager` and `RuleEngine` pre-process the text.
6. `TranslationManager` (NLLB-200) translates the text.
7. `BackTranslationManager` and `ConfidenceManager` verify quality.
8. `TTSManager` (Piper) generates speech.
9. `AudioManager` plays the audio on the USB speaker.
10. `HistoryManager` saves the result.
11. `WatchdogManager` and `ResourceManager` monitor health in the background.

## Module Dependencies

- `main.py` wires all managers.
- `managers/` are independent units that implement the specification.
- `utils/` contains hardware- and OS-specific helpers.
- `config/` provides global configuration.
