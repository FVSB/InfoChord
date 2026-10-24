import os

CHORD_PORT: int = int(os.getenv("CHORD_PORT", "8001"))
HTTP_PORT: int = int(os.getenv("HTTP_PORT", "8000"))
LOG_DIR: str = os.getenv("LOG_DIR", "app/logs")
