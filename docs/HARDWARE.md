# AI Translator OS v1.0 — Hardware Setup

## Target Device

- Raspberry Pi 3 (B / B+)
- Raspberry Pi OS Lite 64-bit
- Docker / Docker Compose

## LCD1602 I2C

| LCD1602 | Raspberry Pi GPIO | Pin Number |
|---------|-------------------|------------|
| GND     | GND               | 6          |
| VCC     | 5V                | 2          |
| SDA     | GPIO2 (SDA)       | 3          |
| SCL     | GPIO3 (SCL)       | 5          |

The I2C address is defined in `config/config.json` (default `0x27` = 39).

## Buttons

All buttons use internal pull-up and connect to GND when pressed.

| Function | GPIO |
|----------|------|
| LEFT     | 17   |
| RIGHT    | 27   |
| SPEAK    | 22   |
| REPLAY   | 23   |
| MENU     | 24   |

## Audio

- USB microphone → audio input
- USB speaker → audio output
- Ensure the device is the ALSA default (`default`).

## Power

Use a stable 5V/2.5A+ power supply. A weak power supply can cause USB audio and model inference failures.

## Enabling I2C and GPIO

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
# Interface Options -> GPIO Remote -> not needed
```

Verify I2C:

```bash
sudo i2cdetect -y 1
```

Verify audio devices:

```bash
arecord -l
aplay -l
```
