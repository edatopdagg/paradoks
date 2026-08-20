from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BACKEND_DIR),
)

from app.services.retriever import Retriever


# Retriever.__init__ çağrılmıyor.
# Böylece DB ve embedding modeli yüklenmez.
retriever = object.__new__(Retriever)


search_queries = [
    "orijinal soru",
    "UE deregistration procedure",
    "network initiated deregistration",
    "UE initiated deregistration",
]


fake_result = {
    "ids": [
        [
            "chunk_a",
            "chunk_b",
            "chunk_bad",
        ],
        [
            "chunk_a",
            "chunk_c",
            "chunk_d",
        ],
        [
            "chunk_a",
            "chunk_b",
            "chunk_e",
        ],
        [
            "chunk_f",
            "chunk_a",
            "chunk_c",
        ],
    ],

    "documents": [
        [
            "A metni",
            "B metni",
            "Threshold dışı metin",
        ],
        [
            "A metni",
            "C metni",
            "D metni",
        ],
        [
            "A metni",
            "B metni",
            "E metni",
        ],
        [
            "F metni",
            "A metni",
            "C metni",
        ],
    ],

    "metadatas": [
        [
            {
                "org": "3GPP",
                "code": "TS 23.502",
                "clause": "4.2.2.3",
            },
            {
                "org": "3GPP",
                "code": "TS 24.501",
                "clause": "5.5",
            },
            {
                "org": "TEST",
                "code": "BAD",
                "clause": "0",
            },
        ],
        [
            {
                "org": "3GPP",
                "code": "TS 23.502",
                "clause": "4.2.2.3",
            },
            {
                "org": "3GPP",
                "code": "TS 23.501",
                "clause": "5.3",
            },
            {
                "org": "3GPP",
                "code": "TS 38.331",
                "clause": "5",
            },
        ],
        [
            {
                "org": "3GPP",
                "code": "TS 23.502",
                "clause": "4.2.2.3",
            },
            {
                "org": "3GPP",
                "code": "TS 24.501",
                "clause": "5.5",
            },
            {
                "org": "ETSI",
                "code": "TS 123 502",
                "clause": "4",
            },
        ],
        [
            {
                "org": "3GPP",
                "code": "TS 29.502",
                "clause": "6",
            },
            {
                "org": "3GPP",
                "code": "TS 23.502",
                "clause": "4.2.2.3",
            },
            {
                "org": "3GPP",
                "code": "TS 23.501",
                "clause": "5.3",
            },
        ],
    ],

    "distances": [
        [
            0.31,
            0.38,
            0.80,
        ],
        [
            0.24,
            0.35,
            0.41,
        ],
        [
            0.27,
            0.33,
            0.40,
        ],
        [
            0.39,
            0.22,
            0.32,
        ],
    ],
}


matches = retriever._merge_results(
    result=fake_result,
    search_queries=search_queries,
)


print()
print("=" * 70)
print("RETRIEVER MERGE TEST")
print("=" * 70)

for index, match in enumerate(
    matches,
    start=1,
):
    print(
        index,
        match["chunk_id"],
        "| distance:",
        match["distance"],
        "| query hit:",
        len(match["matched_queries"]),
    )

print("=" * 70)


# ---------------------------------------------------------
# DOĞRULAMALAR
# ---------------------------------------------------------

ids = [
    match["chunk_id"]
    for match in matches
]


# Threshold dışındaki sonuç gitmeli.
assert "chunk_bad" not in ids


# Duplicate chunk yalnızca bir kez kalmalı.
assert ids.count("chunk_a") == 1


chunk_a = next(
    match
    for match in matches
    if match["chunk_id"] == "chunk_a"
)


# Aynı chunk dört sorguda da bulundu.
assert len(
    chunk_a["matched_queries"]
) == 4


# En iyi (en düşük) distance korunmalı.
assert (
    abs(
        chunk_a["distance"] - 0.22
    )
    < 0.000001
)


# Reranker'a en fazla 6 aday gitmeli.
assert len(matches) <= 6


print()
print("TÜM RETRIEVER MERGE TESTLERİ BAŞARILI")