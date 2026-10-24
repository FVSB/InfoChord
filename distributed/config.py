import os

CHORD_PORT: int = int(os.getenv("CHORD_PORT", "8001"))
HTTP_PORT: int = int(os.getenv("HTTP_PORT", "8000"))
PYRO5_URL: str = os.getenv("PYRO5_URL", "search.search")
DB_PATH: str = os.getenv("DB_PATH", "sqlite:///app/database/database.db")
EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "http://host.docker.internal:1234/v1")
EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "lm-studio")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5-GGUF")
LOG_DIR: str = os.getenv("LOG_DIR", "app/logs")
