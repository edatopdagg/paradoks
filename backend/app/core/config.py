import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(
    __file__
).resolve().parent.parent.parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    ENV_FILE
)


# ---------------------------------------------------------
# EMBEDDING
# ---------------------------------------------------------

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "intfloat/multilingual-e5-small",
)


# ---------------------------------------------------------
# CHROMA DB
# ---------------------------------------------------------

_raw_chroma_db_path = os.getenv(
    "CHROMA_DB_PATH",
    "vector_db",
)

_chroma_path = Path(
    _raw_chroma_db_path
)

if _chroma_path.is_absolute():
    CHROMA_DB_PATH = str(
        _chroma_path
    )
else:
    CHROMA_DB_PATH = str(
        (
            BASE_DIR
            / _chroma_path
        ).resolve()
    )


CHROMA_COLLECTION_NAME = os.getenv(
    "CHROMA_COLLECTION_NAME",
    "telecom_standards",
)


# ---------------------------------------------------------
# EMBEDDING PREFIXES
# ---------------------------------------------------------

QUERY_PREFIX = os.getenv(
    "QUERY_PREFIX",
    "query: ",
)

PASSAGE_PREFIX = os.getenv(
    "PASSAGE_PREFIX",
    "passage: ",
)


# ---------------------------------------------------------
# OLLAMA
# ---------------------------------------------------------

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_CHAT_URL = (
    f"{OLLAMA_BASE_URL}/api/chat"
)

OLLAMA_MODEL_NAME = os.getenv(
    "OLLAMA_MODEL_NAME",
    "qwen3.5:2b-q4_K_M",
)

OLLAMA_TIMEOUT_SECONDS = int(
    os.getenv(
        "OLLAMA_TIMEOUT_SECONDS",
        "180",
    )
)


# ---------------------------------------------------------
# RETRIEVAL
# ---------------------------------------------------------

MAX_RETRIEVAL_DISTANCE = float(
    os.getenv(
        "MAX_RETRIEVAL_DISTANCE",
        "0.43",
    )
)


# ---------------------------------------------------------
# RERANKER
# ---------------------------------------------------------

RERANKER_MODEL_NAME = os.getenv(
    "RERANKER_MODEL_NAME",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)

RERANKER_TOP_K = int(
    os.getenv(
        "RERANKER_TOP_K",
        "2",
    )
)

RERANKER_MAX_LENGTH = int(
    os.getenv(
        "RERANKER_MAX_LENGTH",
        "512",
    )
)

# ---------------------------------------------------------
# V3 SOURCE CATALOG
# ---------------------------------------------------------

_raw_v3_catalog_path = os.getenv(
    "V3_CATALOG_PATH",
    "catalog.sqlite3",
)

_v3_catalog_path = Path(
    _raw_v3_catalog_path
)

if _v3_catalog_path.is_absolute():
    V3_CATALOG_PATH = str(
        _v3_catalog_path
    )
else:
    V3_CATALOG_PATH = str(
        (
            BASE_DIR
            / _v3_catalog_path
        ).resolve()
    )
