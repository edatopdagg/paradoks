"""
Paradoks recursive crawler + Vector DB builder.

Yeni rebuild:

python main.py \
    --seed data/seeds/23041-k00.docx \
    --output-db backend/vector_db_v2 \
    --reset

Mevcut DB üzerinden devam:

python main.py \
    --seed data/seeds/23041-k00.docx \
    --output-db backend/vector_db_v2 \
    --resume

Crawler cache'i tamamen yenileyerek devam:

python main.py \
    --seed data/seeds/23041-k00.docx \
    --output-db backend/vector_db_v2 \
    --resume \
    --refresh-cache
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(
    __file__
).resolve().parent

SRC_DIR = (
    BASE_DIR
    / "src"
)

DEFAULT_CACHE_DIR = (
    BASE_DIR
    / "data"
    / "crawler_cache"
)

sys.path.insert(
    0,
    str(SRC_DIR),
)


from crawler import Crawler
from vector_store import VectorStore
from reference_parser import (
    parse_references_section,
)
from chunker import build_chunks


def read_local_docx(
    file_path: str | Path,
) -> str:
    """
    Local DOCX dosyasındaki paragraph metinlerini okur.
    """

    import docx

    doc = docx.Document(
        str(file_path)
    )

    return "\n".join(
        paragraph.text
        for paragraph
        in doc.paragraphs
    )


def extract_references_text(
    full_text: str,
) -> str:
    """
    Seed dokümanındaki References bölümünü ayırır.
    """

    match = re.search(
        r"\[1\]\s+",
        full_text,
    )

    if not match:
        return full_text

    start_idx = (
        match.start()
    )

    end_idx = (
        full_text.find(
            "1.2\tAbbreviations",
            start_idx,
        )
    )

    if end_idx == -1:
        end_idx = (
            full_text.find(
                "1.2 Abbreviations",
                start_idx,
            )
        )

    if end_idx == -1:
        return full_text[
            start_idx:
        ]

    return full_text[
        start_idx:
        end_idx
    ]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Recursive telecom standard crawler "
            "and Vector DB builder"
        )
    )

    parser.add_argument(
        "--seed",
        required=True,
        help="Seed DOCX path",
    )

    parser.add_argument(
        "--output-db",
        default="backend/vector_db_v2",
        help=(
            "Chroma DB yolu. "
            "Default: backend/vector_db_v2"
        ),
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Output DB varsa çalıştırma "
            "öncesinde tamamen sil."
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Var olan DB'yi koru ve eksik "
            "deterministic chunk ID'lerden devam et."
        ),
    )

    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help=(
            "Crawler disk cache'ini çalıştırma "
            "öncesinde tamamen temizle."
        ),
    )

    parser.add_argument(
        "--cache-dir",
        default=str(
            DEFAULT_CACHE_DIR
        ),
        help=(
            "Crawler cache klasörü. "
            "Default: data/crawler_cache"
        ),
    )

    args = parser.parse_args()

    if (
        args.reset
        and args.resume
    ):
        print(
            "ERROR: --reset ve --resume "
            "aynı anda kullanılamaz."
        )
        sys.exit(1)

    # -----------------------------------------------------
    # PATHLER
    # -----------------------------------------------------
    seed_path = Path(
        args.seed
    )

    if not seed_path.is_absolute():
        seed_path = (
            BASE_DIR
            / seed_path
        )

    output_db = Path(
        args.output_db
    )

    if not output_db.is_absolute():
        output_db = (
            BASE_DIR
            / output_db
        )

    cache_dir = Path(
        args.cache_dir
    )

    if not cache_dir.is_absolute():
        cache_dir = (
            BASE_DIR
            / cache_dir
        )

    # -----------------------------------------------------
    # SEED KONTROL
    # -----------------------------------------------------
    if not seed_path.exists():
        print(
            "ERROR: Seed bulunamadı:",
            seed_path,
        )
        sys.exit(1)

    print("=" * 70)
    print("PARADOKS DATA PIPELINE")
    print("=" * 70)

    print(
        "Seed:",
        seed_path.resolve(),
    )

    print(
        "Vector DB:",
        output_db.resolve(),
    )

    print(
        "Crawler cache:",
        cache_dir.resolve(),
    )

    # -----------------------------------------------------
    # CACHE MODE
    # -----------------------------------------------------
    if args.refresh_cache:
        print()

        if cache_dir.exists():
            print(
                "[CACHE] Mevcut crawler cache "
                "siliniyor..."
            )

            shutil.rmtree(
                cache_dir
            )

        print(
            "[CACHE] Cache temizlendi."
        )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # DB MODE
    # -----------------------------------------------------
    if output_db.exists():

        if args.reset:
            print()
            print(
                "[DB] Mevcut DB siliniyor..."
            )

            shutil.rmtree(
                output_db
            )

        elif args.resume:
            print()
            print(
                "[DB] RESUME MODE"
            )

            print(
                "[DB] Mevcut DB korunacak."
            )

            print(
                "[DB] Zaten indexlenmiş deterministic "
                "chunk ID'leri yeniden embed edilmeyecek."
            )

        else:
            print()
            print(
                "ERROR: Output DB zaten var."
            )

            print(
                "Sıfırdan rebuild için --reset,"
            )

            print(
                "mevcut DB'den devam için --resume kullan."
            )

            sys.exit(1)

    else:
        if args.resume:
            print()
            print(
                "[DB] Resume istendi ancak DB yok."
            )

            print(
                "[DB] Yeni DB oluşturularak devam edilecek."
            )

    # -----------------------------------------------------
    # 1. SEED
    # -----------------------------------------------------
    print()
    print(
        "1. Seed document okunuyor..."
    )

    seed_text = (
        read_local_docx(
            seed_path
        )
    )

    # -----------------------------------------------------
    # 2. REFERENCES
    # -----------------------------------------------------
    print(
        "2. References bölümü çıkarılıyor..."
    )

    ref_section_text = (
        extract_references_text(
            seed_text
        )
    )

    # -----------------------------------------------------
    # 3. PARSE
    # -----------------------------------------------------
    print(
        "3. Seed references parse ediliyor..."
    )

    seed_refs = (
        parse_references_section(
            ref_section_text
        )
    )

    print(
        "   Seed reference sayısı:",
        len(seed_refs),
    )

    # -----------------------------------------------------
    # 4. CRAWLER
    # -----------------------------------------------------
    print()
    print(
        "4. Recursive crawler başlıyor..."
    )

    crawler = Crawler(
        cache_dir=cache_dir
    )

    crawler.seed(
        seed_refs
    )

    results = (
        crawler.run()
    )

    print()
    print(
        "Crawler tamamlandı."
    )

    print(
        "Toplam işlenen reference:",
        len(results),
    )

    print(
        "Başarıyla indirilen document:",
        len(
            crawler.documents
        ),
    )

    # -----------------------------------------------------
    # METADATA MAP
    # -----------------------------------------------------
    resolved_map = {}

    for resolved in results:
        reference = (
            resolved.reference
        )

        key = (
            reference.org,
            reference.code,
        )

        resolved_map[
            key
        ] = resolved

    # -----------------------------------------------------
    # 5. VECTOR STORE
    # -----------------------------------------------------
    print()
    print(
        "5. Vector DB işleme başlıyor..."
    )

    store = VectorStore(
        db_path=output_db,
        collection_name=(
            "telecom_standards"
        ),
    )

    initial_db_count = (
        store.collection.count()
    )

    print(
        "[DB] Başlangıç chunk sayısı:",
        initial_db_count,
    )

    newly_written = 0

    total_documents = len(
        crawler.documents
    )

    zero_chunk_documents = 0

    zero_chunk_list: list[
        tuple[str, str]
    ] = []

    # -----------------------------------------------------
    # 6. CHUNK + EMBED + UPSERT
    # -----------------------------------------------------
    for document_counter, key in enumerate(
        list(
            crawler.documents.keys()
        ),
        start=1,
    ):
        org, code = key

        print()
        print("=" * 70)

        print(
            f"[DOC] "
            f"{document_counter}/"
            f"{total_documents}"
        )

        print(
            f"[DOC] {org} {code}"
        )

        text = (
            crawler.documents.pop(
                key
            )
        )

        resolved = (
            resolved_map.get(
                key
            )
        )

        version = "Latest"
        source_url = None

        if resolved is not None:

            if resolved.version:
                version = (
                    resolved.version
                )

            if resolved.source_url:
                source_url = (
                    resolved.source_url
                )

        chunks = build_chunks(
            document_text=text,
            doc_org=org,
            doc_code=code,
            version=version,
            source_url=source_url,
        )

        print(
            "[DOC] Oluşturulan chunk:",
            len(chunks),
        )

        if not chunks:
            zero_chunk_documents += 1

            zero_chunk_list.append(
                (
                    org,
                    code,
                )
            )

        written = (
            store.upsert_chunks(
                chunks
            )
        )

        newly_written += (
            written
        )

        print(
            "[DOC] Yeni yazılan:",
            written,
        )

        print(
            "[TOTAL] Bu çalışmada yeni yazılan:",
            newly_written,
        )

        print(
            "[TOTAL] DB toplam:",
            store.collection.count(),
        )

    # -----------------------------------------------------
    # FINAL
    # -----------------------------------------------------
    final_db_count = (
        store.collection.count()
    )

    print()
    print("=" * 70)
    print(
        "PIPELINE TAMAMLANDI"
    )
    print("=" * 70)

    print(
        "Toplam document:",
        total_documents,
    )

    print(
        "0 chunk üreten document:",
        zero_chunk_documents,
    )

    print(
        "Başlangıç DB chunk:",
        initial_db_count,
    )

    print(
        "Bu çalışmada yeni yazılan:",
        newly_written,
    )

    print(
        "Final DB chunk:",
        final_db_count,
    )

    print(
        "Vector DB:",
        output_db.resolve(),
    )

    if zero_chunk_list:
        print()
        print("-" * 70)
        print(
            "0 CHUNK URETEN DOKUMANLAR"
        )
        print("-" * 70)

        for org, code in zero_chunk_list:
            print(
                f"{org} {code}"
            )

    print("=" * 70)


if __name__ == "__main__":
    main()
