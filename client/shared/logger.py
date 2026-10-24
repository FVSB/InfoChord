import logging
import json
import time
import os
from datetime import datetime
import inspect
import traceback
import sys

logs_dir = "app/logs"
logs_json = {}

_initialized = False


def setup_logging(log_dir: str = "app/logs") -> None:
    global logs_dir, _initialized
    if _initialized:
        return
    logs_dir = log_dir
    os.makedirs(logs_dir, exist_ok=True)

    log_file_name = f"my_logs_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    log_file_path = os.path.join(logs_dir, log_file_name)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s - %(lineno)d - %(custom_funcName)s - %(message)s"
    )
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(handlers=[file_handler, console_handler], level=logging.INFO)
    _initialized = True


def serialize_logs(filename: str = "logs_container.json") -> None:
    full_path = os.path.join(logs_dir, filename)
    with open(full_path, "w") as f:
        json.dump(logs_json, f, indent=4)


def log_message(message: str, level: str = "INFO", extra_data: dict = {}, func=None) -> None:
    if not _initialized:
        setup_logging(os.getenv("LOG_DIR", "/app/logs"))

    caller_frame = inspect.currentframe().f_back
    caller_line = caller_frame.f_lineno

    if func is None:
        caller_method = caller_frame.f_code.co_name
    else:
        caller_method = func.__name__ if callable(func) else str(func)

    # Do not retain document contents, queries, provider keys or exception text.
    error_type = sys.exc_info()[0]
    message = f'{caller_method}: {error_type.__name__ if error_type else level}'
    frames = traceback.extract_tb(sys.exc_info()[2]) if error_type else []
    message += ' ' + ' > '.join(f'{frame.name}:{frame.lineno}' for frame in frames)
    extra_data = {}
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "extra_data": extra_data,
        "method": caller_method,
        "line": caller_line,
    }
    if len(logs_json) >= 5000:
        logs_json.pop(next(iter(logs_json)))
    logs_json[time.time()] = log_entry

    extra_data["custom_funcName"] = caller_method
    extra_data["line"] = caller_line

    logger = logging.getLogger(__name__)
    logger.log(logging.getLevelName(level), message, extra=extra_data)


if __name__ == "__main__":
    log_message("Test desde shared/logger.py")
    while True:
        serialize_logs()
        time.sleep(30)
