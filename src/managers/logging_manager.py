import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


class LoggingManager:
    def __init__(self, config):
        self.logs_dir = Path(config.get("logs_dir", "/app/logs"))
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def setup(self):
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if not root.handlers:
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            root.addHandler(console)

        for name in ["system", "translation", "audio", "error", "performance"]:
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)
            if not logger.handlers:
                handler = RotatingFileHandler(
                    self.logs_dir / f"{name}.log",
                    maxBytes=1024 * 1024,
                    backupCount=5,
                )
                handler.setFormatter(
                    logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
                )
                logger.addHandler(handler)
