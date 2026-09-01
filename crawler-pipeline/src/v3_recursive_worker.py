"""Kalıcı V3 kuyruğundaki belgeleri işleyen recursive worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from models import DocStatus, Reference
from resolver import resolve
from v3_catalog import V3Catalog
from v3_crawl_queue import V3CrawlQueue
from v3_fetcher import fetch_document
from v3_ingestor import (
    V3DocumentInput,
    V3IngestResult,
    ingest_document,
)


@dataclass(frozen=True)
class WorkerSummary:
    claimed: int
    indexed: int
    blocked: int
    unresolved: int
    failed_or_requeued: int


def _require_indexable_result(
    result: V3IngestResult,
) -> None:
    if result.chunk_count <= 0:
        raise ValueError(
            "Belge aranabilir icerik "
            "chunk'i uretmedi."
        )


def run_worker(
    *,
    catalog_path: str | Path,
    data_root: str | Path,
    max_documents: int,
    max_depth: int | None = None,
    organizations: (
        tuple[str, ...] | None
    ) = None,
    max_attempts: int = 3,
) -> WorkerSummary:
    if max_documents < 1:
        raise ValueError(
            "max_documents en az 1 olmalı."
        )

    catalog = V3Catalog(
        catalog_path
    )

    queue = V3CrawlQueue(
        catalog
    )

    recovered = (
        queue.recover_interrupted_jobs()
    )

    if recovered:
        print(
            "Recovered interrupted jobs:",
            recovered,
        )

    claimed_count = 0
    claimed_document_ids: set[str] = set()
    indexed_count = 0
    blocked_count = 0
    unresolved_count = 0
    failed_count = 0

    try:
        while (
            claimed_count
            < max_documents
        ):
            job = queue.claim_next(
                max_depth=max_depth,
                organizations=organizations,
            excluded_document_ids=tuple(
                claimed_document_ids
            ),
            )

            if job is None:
                print(
                    "No matching pending job."
                )
                break

            claimed_count += 1
            claimed_document_ids.add(
                job.document_id
            )

            label = (
                f"{job.org} {job.code}"
            )

            print(
                "\n" + "=" * 76
            )
            print("JOB:", label)
            print("DEPTH:", job.depth)
            print("ATTEMPT:", job.attempts)

            try:
                reference = Reference(
                    raw_text="",
                    org=job.org,
                    code=job.code,
                    title=job.title,
                )

                resolved = resolve(
                    reference
                )

                print(
                    "RESOLVE STATUS:",
                    resolved.status.value,
                )

                print(
                    "SOURCE:",
                    resolved.source_url or "",
                )

                if (
                    resolved.status
                    == DocStatus.BLOCKED
                ):
                    queue.mark_status(
                        document_id=(
                            job.document_id
                        ),
                        status="blocked",
                        source_url=(
                            resolved.source_url
                            or ""
                        ),
                    )

                    blocked_count += 1
                    continue

                if (
                    resolved.status
                    == DocStatus.UNRESOLVED
                    or not resolved.source_url
                ):
                    queue.mark_status(
                        document_id=(
                            job.document_id
                        ),
                        status="unresolved",
                        source_url=(
                            resolved.source_url
                            or ""
                        ),
                        last_error=(
                            "Kaynak URL "
                            "çözümlenemedi."
                        ),
                    )

                    unresolved_count += 1
                    continue

                fetched = fetch_document(
                    org=job.org,
                    code=job.code,
                    title=job.title,
                    source_url=(
                        resolved.source_url
                    ),
                    output_root=data_root,
                )

                result = ingest_document(
                    catalog=catalog,
                    document=V3DocumentInput(
                        org=fetched.org,
                        code=fetched.code,
                        title=fetched.title,
                        version=(
                            fetched.version
                        ),
                        release=(
                            fetched.release
                        ),
                        source_url=(
                            fetched.source_url
                        ),
                        local_path=(
                            fetched.local_path
                        ),
                        content_sha256=(
                            fetched.content_sha256
                        ),
                        document_text=(
                            fetched.document_text
                        ),
                        page_texts=(
                            fetched.page_texts
                        ),
                    ),
                )

                _require_indexable_result(
                    result
                )

                child_edges = (
                    catalog.connection.execute(
                        """
                        SELECT
                            id,
                            target_document_id
                        FROM reference_edges
                        WHERE source_version_id = ?
                          AND target_document_id
                              IS NOT NULL
                        """,
                        (
                            result.version_id,
                        ),
                    ).fetchall()
                )

                for edge in child_edges:
                    queue.enqueue_document(
                        document_id=(
                            edge[
                                "target_document_id"
                            ]
                        ),
                        depth=job.depth + 1,
                        discovered_from_edge_id=(
                            edge["id"]
                        ),
                    )

                queue.mark_status(
                    document_id=(
                        job.document_id
                    ),
                    status="indexed",
                    source_url=(
                        fetched.source_url
                    ),
                )

                indexed_count += 1

                print(
                    "VERSION:",
                    fetched.version,
                )
                print(
                    "CLAUSES:",
                    result.clause_count,
                )
                print(
                    "CHUNKS:",
                    result.chunk_count,
                )
                print(
                    "REFERENCES:",
                    result.reference_count,
                )
                print(
                    "NEW QUEUE EDGES:",
                    len(child_edges),
                )
                print(
                    "STATUS: indexed"
                )

            except Exception as error:
                next_status = (
                    queue.mark_failure(
                        document_id=(
                            job.document_id
                        ),
                        error=(
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                        max_attempts=(
                            max_attempts
                        ),
                    )
                )

                failed_count += 1

                print(
                    "STATUS:",
                    next_status,
                )
                print(
                    "ERROR:",
                    type(error).__name__,
                    str(error),
                )

    finally:
        print(
            "\nQUEUE STATUS:",
            queue.status_counts(),
        )

        catalog.close()

    return WorkerSummary(
        claimed=claimed_count,
        indexed=indexed_count,
        blocked=blocked_count,
        unresolved=unresolved_count,
        failed_or_requeued=(
            failed_count
        ),
    )