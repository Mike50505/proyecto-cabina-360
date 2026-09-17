import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Small structured formatter that keeps secrets out of custom metadata."""

    reserved = {"password", "token", "authorization", "secret", "refresh", "access"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        metadata = getattr(record, "metadata", None)
        if isinstance(metadata, dict):
            payload["metadata"] = {
                key: value for key, value in metadata.items() if key.lower() not in self.reserved
            }
        return json.dumps(payload, default=str, ensure_ascii=False)

