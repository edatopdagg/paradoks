FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# OCR + scientific/runtime system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-tur \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m pip install \
    --upgrade pip \
    && python -m pip install \
    --no-cache-dir \
    -r requirements.txt

COPY app/ ./app/

# Paradoks data Docker image'in içine girmez.
# VM üzerinde persistent olarak /data'ya bağlanacaktır.
ENV CHROMA_DB_PATH=/data/vector_db
ENV CHROMA_COLLECTION_NAME=telecom_standards
ENV V3_CATALOG_PATH=/data/catalog.sqlite3

ENV PRIORITY_RETRIEVAL_ENABLED=1
ENV PRIORITY_CHROMA_DB_PATH=/data/priority_runtime/vector_db
ENV PRIORITY_CATALOG_PATH=/data/priority_runtime/priority_catalog.sqlite3
ENV PRIORITY_CHROMA_COLLECTION_NAME=telecom_standards_priority
ENV RADIO_PRIORITY_CHROMA_COLLECTION_NAME=telecom_standards_priority

EXPOSE 8001

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=120s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5)"

CMD [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8001"
]
