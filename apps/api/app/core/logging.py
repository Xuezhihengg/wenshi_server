import logging
import sys
from datetime import datetime
from logging import Handler, LogRecord
from pathlib import Path

import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import get_settings


class DateStructuredFileHandler(Handler):
    def __init__(self, log_dir: str, log_file: str, encoding: str = 'utf-8') -> None:
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_file = log_file
        self.encoding = encoding
        self._current_date = ''
        self._stream = None

    def emit(self, record: LogRecord) -> None:
        try:
            stream = self._get_stream()
            stream.write(f'{self.format(record)}\n')
            stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None
        super().close()

    def _get_stream(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self._stream and self._current_date == today:
            return self._stream
        if self._stream:
            self._stream.close()
        self._current_date = today
        path = self.path_for_date(today)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = path.open('a', encoding=self.encoding)
        return self._stream

    def path_for_date(self, date_text: str) -> Path:
        year, month, day = date_text.split('-')
        return self.log_dir / year / month / day / self.log_file


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = DateStructuredFileHandler(settings.log_dir, settings.log_file)
    file_handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
