from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer


V2_DB_PATH = Path(
    r"C:\Users\edato\OneDrive\Masaüstü"
    r"\paradoks-main\crawler-pipeline"
    r"\backend\vector_db_v2"
)

COLLECTION_NAME = "telecom_standards"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

TOP_K = 10


TEST_CASES = [
    {
        "name": "CELL BROADCAST",
        "question": (
            "How is a Cell Broadcast warning "
            "message cancelled?"
        ),
        "expected_codes": {
            "TS 23.041",
        },
        "expected_clauses": {
            "9.1.3.4.3",
            "9.1.3.5.3",
        },
    },
    {
        "name": "5G REGISTRATION",
        "question": (
            "What is the main purpose of a UE "
            "sending a Registration Request "
            "message in 5G?"
        ),
        "expected_codes": {
            "TS 23.502",
            "TS 24.501",
        },
        "expected_clauses": {
            "4.2.2.2.1",
        },
    },
    {
        "name": "SIP INVITE",
        "question": (
            "What is the purpose of the initial "
            "SIP INVITE request?"
        ),
        "expected_codes": {
            "3261",
            "RFC 3261",
        },
        "expected_clauses": {
            "13",
            "13.1",
            "13.2.1",
        },
    },
]


def metadata_value(
    metadata: dict[str, Any],
    key: str,
) -> str:
    return str(
        metadata.get(
            key,
            "",
        )
    ).strip()


def document_exists(
    collection,
    code: str,
) -> int:
    result = collection.get(
        where={
            "code": code,
        },
        include=[
            "metadatas",
        ],
    )

    return len(
        result.get(
            "ids",
            [],
        )
    )


def run_query(
    collection,
    model,
    test_case: dict[str, Any],
) -> None:
    question = test_case[
        "question"
    ]

    print()
    print("=" * 80)
    print(
        "TEST:",
        test_case["name"],
    )
    print("=" * 80)

    print(
        "Soru:",
        question,
    )

    query_embedding = model.encode(
        f"query: {question}",
        normalize_embeddings=True,
    ).tolist()

    result = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=TOP_K,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    ids = result[
        "ids"
    ][0]

    documents = result[
        "documents"
    ][0]

    metadatas = result[
        "metadatas"
    ][0]

    distances = result[
        "distances"
    ][0]

    expected_rank = None

    for rank, (
        chunk_id,
        document,
        metadata,
        distance,
    ) in enumerate(
        zip(
            ids,
            documents,
            metadatas,
            distances,
        ),
        start=1,
    ):
        metadata = (
            metadata
            or {}
        )

        org = metadata_value(
            metadata,
            "org",
        )

        code = metadata_value(
            metadata,
            "code",
        )

        clause = metadata_value(
            metadata,
            "clause",
        )

        title = metadata_value(
            metadata,
            "clause_title",
        )

        print()
        print(
            rank,
            "|",
            org,
            code,
            "| Clause:",
            clause,
            "| Distance:",
            round(
                float(distance),
                4,
            ),
        )

        if title:
            print(
                "   Title:",
                title,
            )

        preview = (
            document
            or ""
        ).replace(
            "\n",
            " ",
        )

        print(
            "  ",
            preview[:240],
        )

        code_match = (
            code
            in test_case[
                "expected_codes"
            ]
        )

        clause_match = (
            not test_case[
                "expected_clauses"
            ]
            or clause
            in test_case[
                "expected_clauses"
            ]
        )

        if (
            expected_rank is None
            and code_match
            and clause_match
        ):
            expected_rank = rank

    print()
    print("-" * 80)

    print(
        "Beklenen kaynak sirasi:",
        expected_rank,
    )

    if expected_rank is None:
        print(
            "SONUC: BEKLENEN KAYNAK "
            "TOP 10 ICINDE YOK"
        )

    elif expected_rank <= 3:
        print(
            "SONUC: BASARILI"
        )

    else:
        print(
            "SONUC: BULUNDU AMA "
            "SIRALAMA GELISTIRILMELI"
        )


def main() -> None:
    print()
    print("=" * 80)
    print(
        "PARADOKS VECTOR DB V2 TEST"
    )
    print("=" * 80)

    print(
        "DB:",
        V2_DB_PATH,
    )

    if not V2_DB_PATH.exists():
        raise SystemExit(
            "V2 DB klasoru bulunamadi."
        )

    client = (
        chromadb.PersistentClient(
            path=str(
                V2_DB_PATH
            )
        )
    )

    collection = (
        client.get_collection(
            COLLECTION_NAME
        )
    )

    print(
        "Toplam chunk:",
        collection.count(),
    )

    print()
    print("-" * 80)
    print(
        "KRITIK DOCUMENT KONTROLU"
    )
    print("-" * 80)

    critical_documents = [
        "TS 23.041",
        "TS 23.502",
        "TS 24.501",
        "3261",
    ]

    for code in critical_documents:
        count = document_exists(
            collection,
            code,
        )

        print(
            code,
            "->",
            count,
            "chunk",
        )

    print()
    print(
        "Embedding modeli yukleniyor..."
    )

    model = SentenceTransformer(
        EMBEDDING_MODEL
    )

    for test_case in TEST_CASES:
        run_query(
            collection,
            model,
            test_case,
        )

    print()
    print("=" * 80)
    print(
        "V2 TESTLERI TAMAMLANDI"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()