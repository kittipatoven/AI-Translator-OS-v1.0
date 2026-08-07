# AI Translator OS v1.0 — Docker Deployment

## Fully Automated Setup (Recommended)

On the Raspberry Pi, copy the project to `/opt/translator` and run:

```bash
sudo chmod +x /opt/translator/scripts/setup.sh
sudo /opt/translator/scripts/setup.sh
```

This script will install Docker (if missing), enable I2C, copy the project to `/opt/translator`, build the container, install the systemd service, and run a health check.

## Manual Build and Run

```bash
cd /opt/translator
sudo docker compose up --build -d
```

The container is:
- **privileged** (required for GPIO and audio)
- **network_mode: none** (offline-only)
- **restart: always**

## Volumes

| Host path | Container path | Purpose         |
|-----------|----------------|-----------------|
| `./config` | `/app/config`   | configuration   |
| `./data`   | `/app/data`     | dictionary, history, language packs |
| `./models` | `/app/models`   | AI models       |
| `./logs`   | `/app/logs`     | log files       |

## Auto-start on Boot

```bash
sudo cp scripts/translator-os.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable translator-os.service
```

## View Logs

```bash
sudo docker logs -f translator-os-translator-1
```

## Restart

```bash
sudo docker compose restart
```

## Offline Update

Place an update package in `/media/usb` or `/media/sdcard` with an `update.json` manifest. `UpdateManager` will detect and apply it on the next boot or check cycle.
