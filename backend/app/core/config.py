import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "intfloat/multilingual-e5-small",
)

chroma_path_value = Path(
    os.getenv("CHROMA_DB_PATH", "vector_db")
)

CHROMA_DB_PATH = (
    chroma_path_value
    if chroma_path_value.is_absolute()
    else BASE_DIR / chroma_path_value
)

CHROMA_COLLECTION_NAME = os.getenv(
    "CHROMA_COLLECTION_NAME",
    "telecom_standards",
)

QUERY_PREFIX = os.getenv(
    "QUERY_PREFIX",
    "query: ",
)

PASSAGE_PREFIX = os.getenv(
    "PASSAGE_PREFIX",
    "passage: ",
)

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"

OLLAMA_MODEL_NAME = os.getenv(
    "OLLAMA_MODEL_NAME",
    "qwen3.5:2b-q4_K_M",
)

OLLAMA_TIMEOUT_SECONDS = int(
    os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")
)

MAX_RETRIEVAL_DISTANCE = float(
    os.getenv("MAX_RETRIEVAL_DISTANCE", "0.43")
)

RERANKER_MODEL_NAME = os.getenv(
    "RERANKER_MODEL_NAME",
    "BAAI/bge-reranker-v2-m3",
)

RERANKER_TOP_K = int(
    os.getenv("RERANKER_TOP_K", "2")
)

RERANKER_MAX_LENGTH = int(
    os.getenv("RERANKER_MAX_LENGTH", "512")
)