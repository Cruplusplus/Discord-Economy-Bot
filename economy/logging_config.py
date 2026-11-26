"""
Configuracion de logging estructurado para el bot.
Usa RotatingFileHandler con formato JSON para mejor observabilidad.
"""

import json
import logging
import logging.handlers
import os
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formateador JSON para logs estructurados."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Agregar campos extra si existen
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "guild_id"):
            log_data["guild_id"] = record.guild_id
        if hasattr(record, "command"):
            log_data["command"] = record.command
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Excepcion
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """
    Configura el sistema de logging global.
    Returns:
        Logger raiz configurado.
    """
    # Configuracion desde variables de entorno
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "logs/bot.log")
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB default
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # Crear directorio de logs si no existe
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Limpiar handlers existentes
    root_logger.handlers.clear()

    # Handler consola (formato simple para desarrollo)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Handler archivo rotativo (formato JSON)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    # Reducir verbosidad de librerias externas
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger con el nombre especificado."""
    return logging.getLogger(name)


class LogContext:
    """Context manager para agregar contexto a logs."""

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)
