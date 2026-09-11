import sqlite3
import time
from pathlib import Path
from typing import Any

import chromadb

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    MAX_RETRIEVAL_DISTANCE,
    V3_CATALOG_PATH,
)
from app.services.embedding_service import EmbeddingService
from app.services.query_normalizer import QueryNormalizer


# Chat pipeline'ın istediği varsayılan sonuç sayısı.
DEFAULT_TOP_K = 3

# Her query varyantı için Chroma'dan daha geniş
# aday havuzu alınır.
#
# Önemli:
# Bu değer reranker'a 20 aday gönderildiği anlamına gelmez.
# Aşağıdaki MAX_MERGED_CANDIDATES ile tekrar sınırlandırılır.
CHROMA_CANDIDATES_PER_VARIANT = 35

# Query expansion sonrasında reranker'a gönderilecek
# maksimum birleşik aday sayısı.
MAX_MERGED_CANDIDATES = 12

# Orijinal sorgu + en fazla 3 teknik varyant.
MAX_QUERY_VARIANTS = 4

# Reciprocal Rank Fusion sabiti.
#
# Büyük değerler farklı query listeleri arasındaki
# rank farklarını daha yumuşak biçimde birleştirir.
RRF_K = 60.0


class Retriever:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.query_normalizer = QueryNormalizer()

        # Explicit document -> latest version_id cache.
        # Ayn? standard?n catalog.sqlite3 ??z?mlemesini
        # her sorguda tekrar yapmamak i?in tutulur.
        self._document_where_cache: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        print(
            "[RETRIEVER] Chroma DB:",
            CHROMA_DB_PATH,
        )

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH)
        )

        self.collection = self.client.get_collection(
            name=CHROMA_COLLECTION_NAME
        )

        print(
            "[RETRIEVER] Collection:",
            CHROMA_COLLECTION_NAME,
        )

        print(
            "[RETRIEVER] Toplam chunk:",
            self.collection.count(),
        )

    @staticmethod
    def _extract_document_identity_from_where(
        where: dict[str, Any] | None,
    ) -> tuple[str, str] | None:
        """
        Chroma filtresindeki org + code kimli?ini ??kar?r.

        Desteklenen ?rnek:

        {
            "$and": [
                {"org": "3GPP"},
                {"code": "TS 23.501"},
            ]
        }

        veya:

        {
            "org": "3GPP",
            "code": "TS 23.501",
        }
        """

        if not where:
            return None

        org = ""
        code = ""

        direct_org = where.get(
            "org"
        )

        direct_code = where.get(
            "code"
        )

        if isinstance(
            direct_org,
            str,
        ):
            org = direct_org.strip()

        if isinstance(
            direct_code,
            str,
        ):
            code = direct_code.strip()

        and_conditions = where.get(
            "$and"
        )

        if isinstance(
            and_conditions,
            list,
        ):

            for condition in and_conditions:

                if not isinstance(
                    condition,
                    dict,
                ):
                    continue

                condition_org = (
                    condition.get(
                        "org"
                    )
                )

                condition_code = (
                    condition.get(
                        "code"
                    )
                )

                if (
                    isinstance(
                        condition_org,
                        str,
                    )
                    and condition_org.strip()
                ):
                    org = (
                        condition_org.strip()
                    )

                if (
                    isinstance(
                        condition_code,
                        str,
                    )
                    and condition_code.strip()
                ):
                    code = (
                        condition_code.strip()
                    )

        if not org or not code:
            return None

        return (
            org,
            code,
        )


    @staticmethod
    def _resolve_catalog_path() -> Path | None:
        """
        Aktif V3 catalog.sqlite3 dosyas?n? bulur.

        ?nce config'teki V3_CATALOG_PATH denenir.
        Ard?ndan CHROMA_DB_PATH'in ?st klas?r?ne bak?l?r.
        """

        candidates = [
            Path(
                str(
                    V3_CATALOG_PATH
                )
            ),
            (
                Path(
                    str(
                        CHROMA_DB_PATH
                    )
                ).parent
                / "catalog.sqlite3"
            ),
        ]

        seen: set[str] = set()

        for candidate in candidates:

            key = str(
                candidate
            ).casefold()

            if key in seen:
                continue

            seen.add(
                key
            )

            if (
                candidate.exists()
                and candidate.is_file()
            ):
                return candidate

        return None


    def _resolve_fast_document_where(
        self,
        where: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """
        Explicit org + code filtresini latest version_id
        filtresine d?n??t?r?r.

        Neden:

        Full Chroma DB ?zerinde:

            org + code ($and)
                ~24 saniye

        ancak:

            version_id
                ~0.16 saniye

        s?rmektedir.

        Bu d?n???m yaln?zca catalog.sqlite3 i?inde
        kesin latest version bulundu?unda yap?l?r.

        ??z?m bulunamazsa mevcut where filtresi aynen
        korunur; yani retrieval davran??? bozulmaz.
        """

        identity = (
            self
            ._extract_document_identity_from_where(
                where
            )
        )

        if identity is None:
            return where

        org, code = identity

        cache_key = (
            org.strip().casefold(),
            code.strip().casefold(),
        )

        cached = (
            self
            ._document_where_cache
            .get(
                cache_key
            )
        )

        if cached is not None:
            return dict(
                cached
            )

        catalog_path = (
            self
            ._resolve_catalog_path()
        )

        if catalog_path is None:

            print(
                "[RETRIEVAL] V3 catalog bulunamad?; "
                "orijinal metadata filtresi kullan?lacak."
            )

            return where

        connection = None

        try:

            connection = (
                sqlite3.connect(
                    str(
                        catalog_path
                    )
                )
            )

            row = (
                connection.execute(
                    """
                    SELECT
                        document_versions.id
                    FROM documents
                    JOIN document_versions
                      ON document_versions.document_id
                         = documents.id
                    WHERE documents.org_key = ?
                      AND documents.code_key = ?
                      AND document_versions.is_latest = 1
                    LIMIT 1
                    """,
                    (
                        cache_key[0],
                        cache_key[1],
                    ),
                )
                .fetchone()
            )

        except sqlite3.Error as error:

            print(
                "[RETRIEVAL] Catalog resolve hatas?:",
                error,
            )

            return where

        finally:

            if connection is not None:
                connection.close()

        if (
            row is None
            or not row[0]
        ):

            print(
                "[RETRIEVAL] Catalog latest version "
                "bulunamad?:",
                org,
                code,
            )

            return where

        resolved_where = {
            "version_id": str(
                row[0]
            )
        }

        self._document_where_cache[
            cache_key
        ] = dict(
            resolved_where
        )

        print(
            "[RETRIEVAL] Fast document filter:",
            f"{org} {code}",
            "->",
            resolved_where[
                "version_id"
            ],
        )

        return resolved_where


    def _merge_results(
        self,
        result: dict[str, Any],
        search_queries: list[str],
    ) -> list[dict[str, Any]]:
        """
        Birden fazla query varyantından gelen sonuçları
        RRF tabanlı olarak birleştirir.

        Amaç:

        1. Aynı chunk'ı yalnızca bir kez tutmak.
        2. En iyi semantic distance değerini korumak.
        3. Chunk'ın hangi query varyantlarında bulunduğunu
           kaydetmek.
        4. Her query içindeki rank bilgisini hesaba katmak.
        5. Her query varyantının en güçlü sonucunun birleşik
           aday havuzunda temsil edilmesini sağlamak.

        Böylece yalnızca global minimum distance'a göre
        yapılan sıralamanın doğru fakat farklı bir query
        varyantında bulunan kaynakları ezmesi engellenir.
        """

        merged: dict[
            str,
            dict[str, Any]
        ] = {}

        # Her query varyantının ilk geçerli sonucunu
        # saklayacağız.
        query_top_chunk_ids: list[str] = []

        all_ids = result.get(
            "ids",
            [],
        )

        all_documents = result.get(
            "documents",
            [],
        )

        all_metadatas = result.get(
            "metadatas",
            [],
        )

        all_distances = result.get(
            "distances",
            [],
        )

        # -------------------------------------------------
        # HER QUERY VARYANTI
        # -------------------------------------------------

        for query_index, search_query in enumerate(
            search_queries
        ):
            if query_index >= len(all_ids):
                continue

            ids = all_ids[
                query_index
            ]

            documents = (
                all_documents[
                    query_index
                ]
                if query_index
                < len(all_documents)
                else []
            )

            metadatas = (
                all_metadatas[
                    query_index
                ]
                if query_index
                < len(all_metadatas)
                else []
            )

            distances = (
                all_distances[
                    query_index
                ]
                if query_index
                < len(all_distances)
                else []
            )

            first_valid_chunk_id: (
                str | None
            ) = None

            # ---------------------------------------------
            # QUERY İÇİNDEKİ SONUÇLAR
            # ---------------------------------------------

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
                if distance is None:
                    continue

                distance_value = float(
                    distance
                )

                if (
                    distance_value
                    > MAX_RETRIEVAL_DISTANCE
                ):
                    continue

                clean_document = (
                    document
                    or ""
                ).strip()

                if not clean_document:
                    continue

                # Bu query varyantındaki ilk geçerli
                # sonucu ayrıca koru.
                if first_valid_chunk_id is None:
                    first_valid_chunk_id = (
                        chunk_id
                    )

                # Reciprocal Rank Fusion katkısı.
                rrf_contribution = (
                    1.0
                    / (
                        RRF_K
                        + rank
                    )
                )

                existing = merged.get(
                    chunk_id
                )

                # -----------------------------------------
                # İLK KEZ GÖRÜLEN CHUNK
                # -----------------------------------------

                if existing is None:
                    merged[
                        chunk_id
                    ] = {
                        "chunk_id": chunk_id,
                        "text": clean_document,
                        "metadata": (
                            metadata
                            or {}
                        ),
                        "distance": (
                            distance_value
                        ),
                        "matched_queries": [
                            search_query
                        ],
                        "matched_query_ranks": {
                            search_query: rank
                        },
                        "best_rank": rank,
                        "fusion_score": (
                            rrf_contribution
                        ),
                    }

                    continue

                # -----------------------------------------
                # AYNI CHUNK BAŞKA QUERY'DE GELDİ
                # -----------------------------------------

                if (
                    search_query
                    not in existing[
                        "matched_queries"
                    ]
                ):
                    existing[
                        "matched_queries"
                    ].append(
                        search_query
                    )

                existing[
                    "matched_query_ranks"
                ][
                    search_query
                ] = rank

                # RRF score birikir.
                existing[
                    "fusion_score"
                ] += (
                    rrf_contribution
                )

                # En iyi rank korunur.
                if (
                    rank
                    < existing[
                        "best_rank"
                    ]
                ):
                    existing[
                        "best_rank"
                    ] = rank

                # En iyi semantic distance korunur.
                if (
                    distance_value
                    < existing[
                        "distance"
                    ]
                ):
                    existing[
                        "distance"
                    ] = (
                        distance_value
                    )

            # Bu query'nin en güçlü sonucu aday havuzunda
            # kaybolmasın.
            if (
                first_valid_chunk_id
                is not None
                and first_valid_chunk_id
                not in query_top_chunk_ids
            ):
                query_top_chunk_ids.append(
                    first_valid_chunk_id
                )

        # -------------------------------------------------
        # DEBUG ALANLARI
        # -------------------------------------------------

        for item in merged.values():
            item[
                "query_hit_count"
            ] = len(
                item[
                    "matched_queries"
                ]
            )

        # -------------------------------------------------
        # RRF SIRALAMASI
        # -------------------------------------------------

        ranked_matches = sorted(
            merged.values(),
            key=lambda item: (
                -item[
                    "fusion_score"
                ],
                -item[
                    "query_hit_count"
                ],
                item[
                    "best_rank"
                ],
                item[
                    "distance"
                ],
            ),
        )

        # -------------------------------------------------
        # QUERY COVERAGE
        # -------------------------------------------------
        #
        # Her query varyantının ilk sonucu önce aday
        # havuzuna alınır.
        #
        # Sonra kalan yerler RRF sıralamasına göre
        # doldurulur.
        #
        # Böylece teknik expansion tarafından bulunan
        # farklı bir doğru kaynak, diğer query'lerin
        # benzer sonuçları yüzünden tamamen kaybolmaz.
        # -------------------------------------------------

        selected: list[
            dict[str, Any]
        ] = []

        selected_ids: set[str] = set()

        for chunk_id in query_top_chunk_ids:
            if (
                len(selected)
                >= MAX_MERGED_CANDIDATES
            ):
                break

            item = merged.get(
                chunk_id
            )

            if item is None:
                continue

            if chunk_id in selected_ids:
                continue

            selected.append(
                item
            )

            selected_ids.add(
                chunk_id
            )

        # -------------------------------------------------
        # KALAN YERLERİ RRF İLE DOLDUR
        # -------------------------------------------------

        for item in ranked_matches:
            if (
                len(selected)
                >= MAX_MERGED_CANDIDATES
            ):
                break

            chunk_id = item[
                "chunk_id"
            ]

            if chunk_id in selected_ids:
                continue

            selected.append(
                item
            )

            selected_ids.add(
                chunk_id
            )

        # -------------------------------------------------
        # FİNAL SIRALAMA
        # -------------------------------------------------
        #
        # Coverage yalnızca seçim garantisidir.
        # Dönen adayları tekrar fusion score'a göre
        # düzenliyoruz.
        # -------------------------------------------------

        selected.sort(
            key=lambda item: (
                -item[
                    "fusion_score"
                ],
                -item[
                    "query_hit_count"
                ],
                item[
                    "best_rank"
                ],
                item[
                    "distance"
                ],
            )
        )

        return selected

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query expansion destekli semantic retrieval.

        Akış:

        1. Kullanıcının sorgusunu temizle.
        2. QueryNormalizer ile teknik varyantlar üret.
        3. Varyantları tek batch'te embed et.
        4. Her varyant için geniş Chroma aday havuzu al.
        5. Distance threshold uygula.
        6. Duplicate chunk'ları birleştir.
        7. RRF ile query varyantlarını fuse et.
        8. Her query'nin en güçlü sonucunu koru.
        9. Reranker'a giden birleşik aday sayısını sınırla.
        """

        clean_query = (
            query
            or ""
        ).strip()

        if not clean_query:
            raise ValueError(
                "Arama sorusu boş olamaz."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k sıfırdan büyük olmalıdır."
            )

        total_start = (
            time.perf_counter()
        )

        # -------------------------------------------------
        # 1. QUERY NORMALIZATION
        # -------------------------------------------------

        normalization_start = (
            time.perf_counter()
        )

        search_queries = (
            self.query_normalizer.normalize(
                clean_query,
                max_variants=(
                    MAX_QUERY_VARIANTS
                ),
            )
        )

        normalization_time = (
            time.perf_counter()
            - normalization_start
        )

        # -------------------------------------------------
        # 2. BATCH QUERY EMBEDDING
        # -------------------------------------------------

        embedding_start = (
            time.perf_counter()
        )

        query_embeddings = (
            self.embedding_service.embed_queries(
                search_queries
            )
        )

        embedding_time = (
            time.perf_counter()
            - embedding_start
        )

        # -------------------------------------------------
        # 3. CHROMA SEARCH DEPTH
        # -------------------------------------------------
        #
        # top_k artık Chroma'nın ham recall derinliğini
        # sınırlamaz.
        #
        # Örneğin chat pipeline top_k=3 gönderse bile
        # her query varyantından en az 20 ham aday alınır.
        # Reranker'a yine en fazla 6 sonuç gider.
        # -------------------------------------------------

        # Explicit document searches already have a precise
        # catalog-backed version_id filter.
        #
        # Keep all normalized query variants for recall, but
        # reduce per-variant Chroma depth. This preserves the
        # multi-query behavior while avoiding an unnecessarily
        # deep filtered ANN search.
        if where:

            chroma_n_results = max(
                top_k,
                12,
            )

        else:

            chroma_n_results = max(
                top_k,
                CHROMA_CANDIDATES_PER_VARIANT,
            )

        # -------------------------------------------------
        # 4. CHROMA SEARCH
        # -------------------------------------------------

        chroma_start = (
            time.perf_counter()
        )

        query_arguments: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": chroma_n_results,
            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        effective_where = (
            self._resolve_fast_document_where(
                where
            )
        )

        if effective_where:
            query_arguments[
                "where"
            ] = effective_where

        result = self.collection.query(
            **query_arguments
        )

        chroma_time = (
            time.perf_counter()
            - chroma_start
        )

        # -------------------------------------------------
        # 5. MERGE + RRF
        # -------------------------------------------------

        merge_start = (
            time.perf_counter()
        )

        matches = self._merge_results(
            result=result,
            search_queries=search_queries,
        )

        merge_time = (
            time.perf_counter()
            - merge_start
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------

        raw_count = sum(
            len(items)
            for items in result.get(
                "ids",
                [],
            )
        )

        print()
        print("=" * 70)

        print(
            "[RETRIEVAL] Kullanıcı sorusu:",
            clean_query,
        )

        print(
            "[RETRIEVAL] Query varyantı:",
            len(search_queries),
        )

        for index, search_query in enumerate(
            search_queries,
            start=1,
        ):
            print(
                f"   {index}. "
                f"{search_query}"
            )

        print(
            "[RETRIEVAL] İstenen top_k:",
            top_k,
        )

        print(
            "[RETRIEVAL] Chroma varyant başına aday:",
            chroma_n_results,
        )

        if where:
            print(
                "[RETRIEVAL] Metadata filtresi:",
                where,
            )

            if effective_where != where:
                print(
                    "[RETRIEVAL] Effective fast filter:",
                    effective_where,
                )

        print(
            "[RETRIEVAL] Toplam ham sonuç:",
            raw_count,
        )

        print(
            "[RETRIEVAL] Fusion sonrası aday:",
            len(matches),
        )

        print("-" * 70)

        for index, match in enumerate(
            matches,
            start=1,
        ):
            metadata = match[
                "metadata"
            ]

            print(
                f"{index}. "
                f"{metadata.get('org', 'Bilinmiyor')} "
                f"{metadata.get('code', 'Bilinmiyor')} | "
                f"Clause: "
                f"{metadata.get('clause', 'Bilinmiyor')} | "
                f"Distance: "
                f"{match['distance']:.4f} | "
                f"Best rank: "
                f"{match['best_rank']} | "
                f"Query hit: "
                f"{match['query_hit_count']} | "
                f"Fusion: "
                f"{match['fusion_score']:.6f}"
            )

        print("-" * 70)

        print(
            f"[PERF] Normalization: "
            f"{normalization_time:.4f} sn"
        )

        print(
            f"[PERF] Embedding batch: "
            f"{embedding_time:.2f} sn"
        )

        print(
            f"[PERF] Chroma Search: "
            f"{chroma_time:.2f} sn"
        )

        print(
            f"[PERF] Fusion: "
            f"{merge_time:.4f} sn"
        )

        print(
            f"[PERF] Retrieval Total: "
            f"{total_time:.2f} sn"
        )

        print("=" * 70)
        print()

        return matches
