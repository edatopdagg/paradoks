# crawler-pipeline (Person A — data ingestion)

Starts from one seed document (e.g. 3GPP TS 23.041), follows its
references recursively, chunks downloaded docs by clause, writes to
a vector DB.

## Flow

```
seed doc
    -> reference_parser (parse reference lines)
    -> resolver (resolve each reference to a real URL)
    -> crawler (download, queue new references, repeat)
    -> chunker (split by clause number)
    -> vector_store (embed, write to DB)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py --seed data/seeds/23041-k00.docx
```

## Modules

| File | Status |
|---|---|
| `src/models.py` | done — shared schema, sync with Person B before changing |
| `src/reference_parser.py` | done — 6 org formats, tested |
| `src/resolver.py` | 3GPP/IETF done, others TODO |
| `src/crawler.py` | queue logic done, real download TODO |
| `src/chunker.py` | done |
| `src/vector_store.py` | interface only, DB connection TODO |

`data/mock/mock_chunks.json` — sample data so Person B can build against
the schema before the real pipeline is running.
