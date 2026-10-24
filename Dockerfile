FROM python:3.11-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 TIKTOKEN_CACHE_DIR=/opt/tiktoken
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && pip check \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
COPY infochord_protocol /app/infochord_protocol
COPY distributed /app/distributed
COPY client /app/client
COPY shared /app/shared
COPY tests /app/tests
COPY scripts /app/scripts
ENV PYTHONPATH=/app:/app/distributed LOG_DIR=/app/logs \
    DB_PATH=sqlite:////app/database/database.db
RUN mkdir -p /app/database /app/logs /app/downloads
CMD ["python", "distributed/server.py"]
