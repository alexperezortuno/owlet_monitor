# utils/logging.py
import logging
from logging.config import dictConfig

logging_config = {
    "version": 1,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s %(levelname)s %(module)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "level": "INFO"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    }
}


def configure_logging():
    dictConfig(logging_config)
