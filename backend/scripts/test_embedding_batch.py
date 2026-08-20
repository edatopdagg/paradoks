from pathlib import Path
import math
import sys


BACKEND_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BACKEND_DIR),
)

from app.services.embedding_service import EmbeddingService


service = EmbeddingService()


queries = [
    "telefon şebekeden kendi kendine çıkış yapıyorsa bunun prosedürü neydi?",
    "UE deregistration procedure",
    "network initiated deregistration",
    "UE initiated deregistration",
]


print()
print("=" * 70)
print("EMBEDDING BATCH TEST")
print("=" * 70)


# ---------------------------------------------------------
# 1. BATCH EMBEDDING
# ---------------------------------------------------------

batch_embeddings = service.embed_queries(
    queries
)

print(
    "Query sayısı:",
    len(queries),
)

print(
    "Embedding sayısı:",
    len(batch_embeddings),
)

print(
    "Embedding boyutu:",
    len(batch_embeddings[0]),
)


assert (
    len(batch_embeddings)
    == len(queries)
)

assert (
    len(batch_embeddings[0])
    == 384
)


# ---------------------------------------------------------
# 2. NORMALIZATION TEST
# ---------------------------------------------------------

for index, embedding in enumerate(
    batch_embeddings,
    start=1,
):
    norm = math.sqrt(
        sum(
            value * value
            for value in embedding
        )
    )

    print(
        f"{index}. norm:",
        f"{norm:.6f}",
    )

    assert abs(
        norm - 1.0
    ) < 0.001


# ---------------------------------------------------------
# 3. TEKLİ / BATCH TUTARLILIĞI
# ---------------------------------------------------------

single_embedding = service.embed_query(
    queries[0]
)

batch_first = batch_embeddings[0]

max_difference = max(
    abs(
        single_value
        - batch_value
    )
    for single_value, batch_value
    in zip(
        single_embedding,
        batch_first,
    )
)

print(
    "Tekli-batch maksimum fark:",
    max_difference,
)

assert max_difference < 0.0001


print()
print(
    "TÜM EMBEDDING BATCH TESTLERİ BAŞARILI"
)
print("=" * 70)