from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import chromadb
import numpy as np

from app.core.config import (
    PASSAGE_PREFIX,
    PRIORITY_CATALOG_PATH,
    PRIORITY_CHROMA_COLLECTION_NAME,
    PRIORITY_CHROMA_DB_PATH,
    PRIORITY_MAX_DISTANCE,
    PRIORITY_MIN_RESULTS,
    PRIORITY_RETRIEVAL_ENABLED,
    PRIORITY_ROUTER_MIN_SCORE,
    PRIORITY_ROUTER_TOP_K,
)
from app.services.retriever import (
    CHROMA_CANDIDATES_PER_VARIANT,
    MAX_QUERY_VARIANTS,
    Retriever,
)


_TECHNICAL_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+"
    r"(?:[+./-][A-Za-z0-9]+)*"
)


class TieredRetriever:
    """
    Paradoks iki katmanlı retrieval.

    Tier 1:
        priority/front-shelf Chroma

    Tier 2:
        mevcut full V3 Chroma

    Dışarıya mevcut Retriever ile aynı search()
    sözleşmesini sunar.

    Önemli:
        self.collection bilinçli olarak full/back-shelf
        collection'ını göstermeye devam eder.

    Böylece chat_service içindeki mevcut targeted fallback
    ve direct collection.get() kullanımları bozulmaz.
    """

    def __init__(self) -> None:

        # ----------------------------------------------------
        # BACK SHELF
        # ----------------------------------------------------

        self.back_retriever = Retriever()

        # Mevcut kodla compatibility.
        self.embedding_service = (
            self.back_retriever.embedding_service
        )

        self.query_normalizer = (
            self.back_retriever.query_normalizer
        )

        self.client = (
            self.back_retriever.client
        )

        self.collection = (
            self.back_retriever.collection
        )

        # ----------------------------------------------------
        # PRIORITY STATE
        # ----------------------------------------------------

        self.priority_enabled = False

        self.priority_client = None
        self.priority_collection = None

        self._priority_documents: list[
            dict[str, str]
        ] = []

        self._priority_document_embeddings = None

        self._priority_signal_sets: list[
            set[str]
        ] = []

        self._priority_signal_vocabulary: set[
            str
        ] = set()

        # ----------------------------------------------------
        # OPTIONAL FRONT SHELF
        # ----------------------------------------------------

        if not PRIORITY_RETRIEVAL_ENABLED:

            print(
                "[TIERED] Priority retrieval disabled."
            )

            return

        if not PRIORITY_CHROMA_DB_PATH:

            print(
                "[TIERED] Priority Chroma path missing; "
                "using back shelf only."
            )

            return

        if not PRIORITY_CATALOG_PATH:

            print(
                "[TIERED] Priority catalog path missing; "
                "using back shelf only."
            )

            return

        priority_db_path = Path(
            PRIORITY_CHROMA_DB_PATH
        )

        priority_catalog_path = Path(
            PRIORITY_CATALOG_PATH
        )

        if not priority_db_path.exists():

            print(
                "[TIERED] Priority Chroma does not exist:",
                priority_db_path,
            )

            return

        if not priority_catalog_path.exists():

            print(
                "[TIERED] Priority catalog does not exist:",
                priority_catalog_path,
            )

            return

        try:

            self.priority_client = (
                chromadb.PersistentClient(
                    path=str(
                        priority_db_path
                    )
                )
            )

            self.priority_collection = (
                self.priority_client.get_collection(
                    name=(
                        PRIORITY_CHROMA_COLLECTION_NAME
                    )
                )
            )

            self._load_priority_documents(
                priority_catalog_path
            )

            self._build_priority_document_index()

            self.priority_enabled = True

        except Exception as error:

            print(
                "[TIERED] Priority initialization failed:",
                error,
            )

            self.priority_client = None
            self.priority_collection = None
            self.priority_enabled = False

            return

        print(
            "[TIERED] Priority collection:",
            PRIORITY_CHROMA_COLLECTION_NAME,
        )

        print(
            "[TIERED] Priority chunks:",
            self.priority_collection.count(),
        )

        print(
            "[TIERED] Priority canonical documents:",
            len(
                self._priority_documents
            ),
        )


    # ========================================================
    # DOCUMENT INDEX
    # ========================================================

    def _load_priority_documents(
        self,
        catalog_path: Path,
    ) -> None:

        connection = sqlite3.connect(
            catalog_path
        )

        connection.row_factory = sqlite3.Row

        try:

            rows = connection.execute(
                """
                SELECT
                    id,
                    org,
                    code,
                    title
                FROM documents
                ORDER BY org, code
                """
            ).fetchall()

        finally:

            connection.close()

        self._priority_documents = [
            {
                "id": str(
                    row["id"]
                ),
                "org": str(
                    row["org"]
                    or ""
                ),
                "code": str(
                    row["code"]
                    or ""
                ),
                "title": str(
                    row["title"]
                    or ""
                ),
            }
            for row in rows
        ]


    @staticmethod
    def _normalize_signal(
        value: str,
    ) -> str:

        return (
            value
            .casefold()
            .strip()
            .rstrip("+")
        )


    @classmethod
    def _document_signals(
        cls,
        document: dict[str, str],
    ) -> set[str]:
        """
        Belge kimliğinden yalnız gerçekten teknik ve
        ayırt edici tokenları çıkarır.

        Ör:
        DAB
        DVB-T2
        RDS
        RBDS
        WEA
        CBC
        BSC
        5G
        48.049

        Normal kelimeler lexical boost üretmez.
        """

        identity = " ".join(
            (
                document.get(
                    "org",
                    "",
                ),
                document.get(
                    "code",
                    "",
                ),
                document.get(
                    "title",
                    "",
                ),
            )
        )

        raw_tokens = (
            _TECHNICAL_TOKEN_RE.findall(
                identity
            )
        )

        signals: set[str] = set()

        for raw in raw_tokens:

            clean = (
                raw.strip()
            )

            if not clean:
                continue

            has_digit = any(
                character.isdigit()
                for character in clean
            )

            has_separator = any(
                character in clean
                for character in (
                    "-",
                    ".",
                    "/",
                    "+",
                )
            )

            is_acronym = (
                clean.upper() == clean
                and clean.lower() != clean
                and 2 <= len(clean) <= 10
            )

            if not (
                has_digit
                or has_separator
                or is_acronym
            ):

                continue

            normalized = (
                cls._normalize_signal(
                    clean
                )
            )

            if normalized:

                signals.add(
                    normalized
                )

        return signals


    def _query_signals(
        self,
        query: str,
    ) -> set[str]:
        """
        Query'deki her kelimeyi boost etmez.

        Yalnız priority document kimliklerinde zaten
        bulunan teknik tokenları kabul eder.

        Bu sayede:
        'arasında', 'hangi', Türkçe ek parçaları vb.
        lexical boost üretemez.
        """

        raw_tokens = (
            _TECHNICAL_TOKEN_RE.findall(
                query
                or ""
            )
        )

        normalized_tokens = {
            self._normalize_signal(
                token
            )
            for token in raw_tokens
            if token.strip()
        }

        return (
            normalized_tokens
            & self._priority_signal_vocabulary
        )


    def _build_priority_document_index(
        self,
    ) -> None:

        if not self._priority_documents:

            raise RuntimeError(
                "Priority document catalog empty."
            )

        identity_texts = []

        self._priority_signal_sets = []

        signal_vocabulary: set[
            str
        ] = set()

        for document in self._priority_documents:

            identity = (
                f"{document['org']} "
                f"{document['code']} — "
                f"{document['title']}"
            )

            identity_texts.append(
                f"{PASSAGE_PREFIX}{identity}"
            )

            signals = (
                self._document_signals(
                    document
                )
            )

            self._priority_signal_sets.append(
                signals
            )

            signal_vocabulary.update(
                signals
            )

        self._priority_signal_vocabulary = (
            signal_vocabulary
        )

        embeddings = (
            self.embedding_service.model.encode(
                identity_texts,
                batch_size=min(
                    16,
                    len(
                        identity_texts
                    ),
                ),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )

        self._priority_document_embeddings = (
            np.asarray(
                embeddings,
                dtype=np.float32,
            )
        )


    # ========================================================
    # ROUTER
    # ========================================================

    def _route_priority_documents(
        self,
        query: str,
    ) -> tuple[
        list[dict[str, str]],
        float,
    ]:

        if (
            self._priority_document_embeddings
            is None
        ):

            return (
                [],
                0.0,
            )

        query_embedding = (
            self.embedding_service.embed_query(
                query
            )
        )

        query_vector = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        semantic_scores = (
            self._priority_document_embeddings
            @ query_vector
        )

        query_signals = (
            self._query_signals(
                query
            )
        )

        final_scores = (
            semantic_scores.copy()
        )

        for index, document_signals in enumerate(
            self._priority_signal_sets
        ):

            overlap = (
                query_signals
                & document_signals
            )

            lexical_bonus = min(
                0.08
                * len(
                    overlap
                ),
                0.16,
            )

            final_scores[
                index
            ] += lexical_bonus

        ranking = np.argsort(
            -final_scores
        )

        selected = [
            self._priority_documents[
                int(index)
            ]
            for index in ranking[
                :PRIORITY_ROUTER_TOP_K
            ]
        ]

        top_score = float(
            final_scores[
                int(
                    ranking[0]
                )
            ]
        )

        print(
            "[TIERED] Router top score:",
            f"{top_score:.4f}",
        )

        for rank, index in enumerate(
            ranking[
                :PRIORITY_ROUTER_TOP_K
            ],
            start=1,
        ):

            document = (
                self._priority_documents[
                    int(index)
                ]
            )

            print(
                f"[TIERED] Router {rank}: "
                f"{document['org']} "
                f"{document['code']} | "
                f"{float(final_scores[int(index)]):.4f}"
            )

        return (
            selected,
            top_score,
        )


    # ========================================================
    # PRIORITY CHROMA HELPERS
    # ========================================================

    @staticmethod
    def _document_key(
        org: Any,
        code: Any,
    ) -> tuple[str, str]:

        return (
            str(
                org
                or ""
            )
            .strip()
            .casefold(),

            str(
                code
                or ""
            )
            .strip()
            .casefold(),
        )


    def _filter_result_to_documents(
        self,
        result: dict[str, Any],
        documents: list[
            dict[str, str]
        ],
    ) -> dict[str, Any]:

        allowed_keys = {
            self._document_key(
                document[
                    "org"
                ],
                document[
                    "code"
                ],
            )
            for document in documents
        }

        filtered: dict[
            str,
            list[Any]
        ] = {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "distances": [],
        }

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

        for query_index in range(
            len(
                all_ids
            )
        ):

            ids = (
                all_ids[
                    query_index
                ]
            )

            documents_for_query = (
                all_documents[
                    query_index
                ]
                if query_index
                < len(
                    all_documents
                )
                else []
            )

            metadatas = (
                all_metadatas[
                    query_index
                ]
                if query_index
                < len(
                    all_metadatas
                )
                else []
            )

            distances = (
                all_distances[
                    query_index
                ]
                if query_index
                < len(
                    all_distances
                )
                else []
            )

            filtered_ids = []
            filtered_documents = []
            filtered_metadatas = []
            filtered_distances = []

            for (
                chunk_id,
                document_text,
                metadata,
                distance,
            ) in zip(
                ids,
                documents_for_query,
                metadatas,
                distances,
            ):

                clean_metadata = (
                    metadata
                    or {}
                )

                key = (
                    self._document_key(
                        clean_metadata.get(
                            "org"
                        ),
                        clean_metadata.get(
                            "code"
                        ),
                    )
                )

                if key not in allowed_keys:

                    continue

                filtered_ids.append(
                    chunk_id
                )

                filtered_documents.append(
                    document_text
                )

                filtered_metadatas.append(
                    clean_metadata
                )

                filtered_distances.append(
                    distance
                )

            filtered[
                "ids"
            ].append(
                filtered_ids
            )

            filtered[
                "documents"
            ].append(
                filtered_documents
            )

            filtered[
                "metadatas"
            ].append(
                filtered_metadatas
            )

            filtered[
                "distances"
            ].append(
                filtered_distances
            )

        return filtered


    def _priority_search(
        self,
        query: str,
        top_k: int,
        where: dict[
            str,
            Any
        ] | None,
        routed_documents: list[
            dict[str, str]
        ] | None,
    ) -> list[
        dict[str, Any]
    ]:

        if (
            not self.priority_enabled
            or self.priority_collection
            is None
        ):

            return []

        search_queries = (
            self.query_normalizer.normalize(
                query,
                max_variants=(
                    MAX_QUERY_VARIANTS
                ),
            )
        )

        query_embeddings = (
            self.embedding_service.embed_queries(
                search_queries
            )
        )

        chroma_n_results = max(
            top_k,
            CHROMA_CANDIDATES_PER_VARIANT,
        )

        arguments: dict[
            str,
            Any
        ] = {
            "query_embeddings": (
                query_embeddings
            ),
            "n_results": (
                chroma_n_results
            ),
            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        if where:

            arguments[
                "where"
            ] = where

        started = (
            time.perf_counter()
        )

        result = (
            self.priority_collection.query(
                **arguments
            )
        )

        chroma_time = (
            time.perf_counter()
            - started
        )

        if (
            routed_documents
            and not where
        ):

            result = (
                self._filter_result_to_documents(
                    result,
                    routed_documents,
                )
            )

        matches = (
            self.back_retriever._merge_results(
                result=result,
                search_queries=(
                    search_queries
                ),
            )
        )

        for match in matches:

            metadata = (
                match.get(
                    "metadata",
                    {}
                )
            )

            metadata[
                "retrieval_tier"
            ] = "priority"

        print(
            "[TIERED] Priority Chroma:",
            f"{chroma_time:.4f} sn",
        )

        print(
            "[TIERED] Priority candidates:",
            len(
                matches
            ),
        )

        return matches


    # ========================================================
    # PUBLIC SEARCH
    # ========================================================

    def search(
        self,
        query: str,
        top_k: int = 3,
        where: dict[
            str,
            Any
        ] | None = None,
    ) -> list[
        dict[str, Any]
    ]:

        clean_query = (
            query
            or ""
        ).strip()

        if not clean_query:

            raise ValueError(
                "Arama sorusu boş olamaz."
            )

        # ----------------------------------------------------
        # PRIORITY DISABLED
        # ----------------------------------------------------

        if not self.priority_enabled:

            return (
                self.back_retriever.search(
                    query=clean_query,
                    top_k=top_k,
                    where=where,
                )
            )

        # ----------------------------------------------------
        # EXPLICIT DOCUMENT FILTER
        # ----------------------------------------------------
        #
        # Kullanıcı doğrudan bir doküman belirtmişse
        # router gereksizdir.
        #
        # Ön rafta varsa kullan, yoksa back shelf'e düş.
        # ----------------------------------------------------

        if where:

            priority_matches = (
                self._priority_search(
                    query=clean_query,
                    top_k=top_k,
                    where=where,
                    routed_documents=None,
                )
            )

            if priority_matches:

                print(
                    "[TIERED] Selected tier: PRIORITY "
                    "(explicit document)"
                )

                return priority_matches

            print(
                "[TIERED] Explicit document not found "
                "in priority shelf; fallback to BACK."
            )

            return (
                self.back_retriever.search(
                    query=clean_query,
                    top_k=top_k,
                    where=where,
                )
            )

        # ----------------------------------------------------
        # DOCUMENT ROUTER
        # ----------------------------------------------------

        routed_documents, router_score = (
            self._route_priority_documents(
                clean_query
            )
        )

        if (
            not routed_documents
            or router_score
            < PRIORITY_ROUTER_MIN_SCORE
        ):

            print(
                "[TIERED] Router confidence insufficient; "
                "fallback to BACK."
            )

            return (
                self.back_retriever.search(
                    query=clean_query,
                    top_k=top_k,
                    where=None,
                )
            )

        # ----------------------------------------------------
        # FRONT SHELF
        # ----------------------------------------------------

        priority_matches = (
            self._priority_search(
                query=clean_query,
                top_k=top_k,
                where=None,
                routed_documents=(
                    routed_documents
                ),
            )
        )

        if not priority_matches:

            print(
                "[TIERED] Priority returned no candidates; "
                "fallback to BACK."
            )

            return (
                self.back_retriever.search(
                    query=clean_query,
                    top_k=top_k,
                    where=None,
                )
            )

        best_distance = min(
            float(
                match.get(
                    "distance",
                    1.0,
                )
            )
            for match in priority_matches
        )

        strong_enough = (
            len(
                priority_matches
            )
            >= PRIORITY_MIN_RESULTS
            and best_distance
            <= PRIORITY_MAX_DISTANCE
        )

        print(
            "[TIERED] Priority best distance:",
            f"{best_distance:.4f}",
        )

        if strong_enough:

            print(
                "[TIERED] Selected tier: PRIORITY"
            )

            return priority_matches

        print(
            "[TIERED] Priority evidence weak; "
            "fallback to BACK."
        )

        return (
            self.back_retriever.search(
                query=clean_query,
                top_k=top_k,
                where=None,
            )
        )
