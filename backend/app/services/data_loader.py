import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_FILE = BASE_DIR / "data" / "mock_chunks.json"


def load_chunks() -> list[dict]:
    with DATA_FILE.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    return chunks