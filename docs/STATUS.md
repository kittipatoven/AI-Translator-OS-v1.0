# AI Translator OS v1.0 — Detailed Status / Audit

Date: 2026-08-07
Goal: Verify if the system can translate all target languages 100% offline.

**Short answer: No — the project structure is ready, but the core AI executables and multi-language TTS voices are not yet wired in.**

## What is Working

- Project structure, `.windsurfrules`, documentation (`docs/*.md`).
- `config/config.json`, `data/dictionary.json`, `data/language_packs/*.json`.
- `scripts/download_models.py` can download Whisper, NLLB, and Piper assets from Hugging Face.
- `scripts/setup.sh` automates Docker/systemd installation on Raspberry Pi.
- `docker-compose.yml` is configured for offline `network_mode: none`.
- `src/main.py` correctly wires all managers into a continuous loop.
- Python syntax of all `src/` and `scripts/` files passes `compileall`.
- `WatchdogManager`, `BackupManager`, `UpdateManager`, `ResourceManager` are functional.
- `LCDManager` and `ButtonManager` have hardware-specific code for the LCD1602 and GPIO buttons.
- `AudioManager` uses `arecord` / `aplay` for capture and playback.

## Critical Blockers for 100% Translation

### 1. Translation is Not Actually Wired to NLLB-200

- File: `src/managers/translation_manager.py`
- It calls a non-existent `translate` executable:
  ```python
  self.executable = "translate"
  cmd = [self.executable, "--source", source, "--target", target, "--text", text]
  ```
- There is no CTranslate2, fairseq, or NLLB runtime in the container.
- Result: It will always return `[TRANSLATE ERROR] <text>` or `[NO-MODEL] <text>`.
- **Impact:** No language can be translated at all, regardless of language pack.

### 2. Whisper.cpp Speech Recognition is Not Installed

- File: `src/managers/speech_manager.py`
- It calls `whisper-cli` as an external executable.
- The `Dockerfile` does **not** build or install `whisper-cli` or `whisper.cpp`.
- Result: `subprocess.CalledProcessError` when trying to transcribe audio.
- **Impact:** The input audio cannot be converted to text.

### 3. Piper TTS is Not Installed and Only English Voice is Present

- File: `src/managers/tts_manager.py`
- It calls `piper` as an external executable.
- The `Dockerfile` does **not** build or install `piper`.
- Current model folder (`models/piper/`) only contains one English voice (`en_US-lessac-low`).
- `TTSManager` always uses the **first `.onnx` file** it finds, ignoring the language pack's `piper_voice`.
- **Impact:**
  - `th-en` (target English) can speak if the English model exists.
  - `en-th` (target Thai), `zh`, `ko`, `my` will speak Thai/Chinese/Korean/Myanmar text with an **English voice**, or fail.

### 4. Missing TTS Voices for Non-English Targets

- Target languages: Thai, Chinese, Korean, Myanmar.
- Piper does not include voices for all of these in the default `rhasspy/piper-voices` set.
- To support them, you need either:
  - Piper voices for each target language, or
  - A fallback TTS engine (e.g., eSpeak, Coqui, local Thai TTS).

### 5. `ConversationManager` Ignores the Selected TTS Voice

- File: `src/managers/conversation_manager.py`
- It calls `self.tts.speak(translated)` without passing the pack's `piper_voice`.
- **Impact:** Even if the correct Piper voice is downloaded, the system will not use it.

### 6. `DictionaryManager` is Broken Against `data/dictionary.json`

- File: `src/managers/dictionary_manager.py`
- `apply` signature is `apply(self, text, source)` but `conversation_manager.py` calls `self.dictionary.apply(source_text)` with one argument.
- The dictionary JSON now uses this structure:
  ```json
  {
    "term": {
      "translations": { "tha_Thai": "..." },
      "do_not_translate": true
    }
  }
  ```
- `apply()` treats the value as a plain string, which will cause a `TypeError` or produce invalid output.
- **Impact:** The custom dictionary will crash the pipeline.

### 7. `RuleEngine` Protected-Term List is Incomplete

- File: `src/managers/rule_engine.py`
- `_PROTECTED` only contains ~10 terms; `.windsurfrules` lists ~40 technical/brand terms to protect.
- **Impact:** Terms like `GPU`, `Docker`, `Raspberry Pi` may be translated when they should not be.

### 8. No Noise Reduction / VAD Module

- `NoiseReduction` and `VoiceActivityDetection` are mentioned in the spec but do not exist in `src/managers/` or `src/modules/`.
- `conversation_manager.py` uses a fixed `record_duration` (default 5 seconds).
- **Impact:** Recordings may include silence/background noise, and the user must hold the button timing. This does not match the "auto VAD" design.

### 9. Only Two Language Packs Are Defined

- `data/language_packs/` only has `en-th.json` and `th-en.json`.
- Missing: `th-zh`, `th-ko`, `th-my`, `zh-th`, `ko-th`, `my-th`, etc.
- Even if added, the translation and TTS blockers above still prevent them from working.

### 10. Back-Translation Quality Check is Too Simple

- File: `src/managers/back_translation_manager.py`
- Uses `difflib.SequenceMatcher` on raw strings.
- Does not handle Thai/Chinese scripts, word segmentation, or semantic meaning.
- **Impact:** Confidence score will be unreliable, especially for Thai, Chinese, Korean, and Myanmar.

### 11. Dockerfile Does Not Build AI Binaries

- File: `Dockerfile`
- It only installs Python packages, `smbus2`, `pyaudio`, etc.
- It does **not** compile or install:
  - `whisper-cli` (Whisper.cpp)
  - `piper` (Piper TTS)
  - CTranslate2/Fairseq for NLLB
- **Impact:** The container will not have the executables the Python code tries to call.

### 12. Model Manifest / Checksum Not Checked

- `ModelManager` can compute SHA256 if a `manifest.json` exists, but the downloaded models do not include a manifest.
- The `setup.sh` only checks that the model directories are not empty; it does not verify integrity.

## Summary of What is Needed for 100% Offline All-Language Translation

1. **Integrate a real NLLB-200 runtime** (e.g., `ctranslate2` with `transformers` tokenizer) inside the container.
2. **Build or install `whisper-cli`** in the Dockerfile (or use `whisper` Python package as a fallback).
3. **Build or install `piper`** in the Dockerfile.
4. **Download the correct Piper voices** for every target language.
5. **Make `TTSManager` and `ConversationManager` select the correct voice** from the active language pack.
6. **Fix `DictionaryManager.apply()`** to match the JSON format and the caller.
7. **Expand `RuleEngine._PROTECTED`** to the full list from `.windsurfrules`.
8. **Add language packs** for Thai, English, Chinese, Korean, Myanmar.
9. **Implement Noise Reduction and VAD** modules, and wire them into the audio pipeline.
10. **Improve back-translation and confidence** with language-aware checks.
11. **Add model integrity verification** (manifest + checksums) before starting.

## Verdict

The current codebase is a solid **skeleton and control layer**, but the **AI pipeline is not end-to-end functional yet**. After completing the items above, the system can be tested on real hardware for all supported languages.
