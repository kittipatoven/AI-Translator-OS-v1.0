# AI Translator OS v1.0 — Test Plan

## 1. Unit Tests

Each manager in `src/managers/` should have a matching test in `tests/`.

### ConfigManager

- load valid JSON
- load missing file fallback
- get nested keys with default

### ModelManager

- list model files
- compute SHA256 checksum
- verify checksum against manifest

### ResourceManager

- read CPU, RAM, temperature, disk
- clean cache when threshold is exceeded

### WatchdogManager

- register a monitor
- trigger restart on failed check
- stop cleanly

## 2. Hardware Tests

### LCD

- `i2cdetect -y 1` finds device.
- LCD displays `Hello` on both lines.

### Buttons

- Press each button; short and long press detected.

### Audio

- Record and play a sample using `arecord` and `aplay`.

### GPIO

- `/dev/gpiomem` is present.
- Buttons register state changes.

## 3. Integration Tests

- Full pipeline with a known WAV file.
- Speech → text → translation → TTS.
- Confidence score above threshold for clear input.

## 4. Long-running Stability

- Run for 24+ hours with periodic button presses.
- Watchdog restarts any hung module.
- Logs rotate without filling storage.
