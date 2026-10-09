from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.schemas import (
    ChatRequest,
    ChatResponse,
    EvidenceRequest,
    EvidenceResponse,
    SourceClauseResponse,
)
from app.services.chat_orchestrator import (
    generate_chat_response,
)
from app.services.compliance_service import (
    compare_documents,
)
from app.services.evidence_service import (
    generate_evidence,
)
from app.services.source_service import (
    get_source_clause,
)


app = FastAPI()


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Paradoks API çalışıyor"
    }


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# ---------------------------------------------------------
# CHAT
# ---------------------------------------------------------

@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
) -> ChatResponse:

    result = generate_chat_response(
        message=request.message,
        conversation_id=(
            request.conversation_id
        ),
        domain=request.domain,
    )

    return ChatResponse(
        **result
    )


# ---------------------------------------------------------
# EVIDENCE
# ---------------------------------------------------------

@app.post(
    "/evidence",
    response_model=EvidenceResponse,
)
def evidence(
    request: EvidenceRequest,
) -> EvidenceResponse:

    try:
        result = generate_evidence(
            message=request.message,
            domain=request.domain,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return EvidenceResponse(
        **result
    )


# ---------------------------------------------------------
# SOURCE CLAUSE VIEWER
# ---------------------------------------------------------

@app.get(
    "/sources/{version_id}/clauses/{clause_id}",
    response_model=SourceClauseResponse,
)
def source_clause(
    version_id: str,
    clause_id: str,
) -> SourceClauseResponse:

    try:
        result = get_source_clause(
            version_id=version_id,
            clause_id=clause_id,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "V3 source catalog is unavailable."
            ),
        ) from error

    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail=(
                "Requested source clause was not found."
            ),
        ) from error

    return SourceClauseResponse(
        **result
    )


# ---------------------------------------------------------
# COMPLIANCE / SPECIFICATION COMPARISON
# ---------------------------------------------------------

@app.post("/compliance/compare")
async def compare_compliance(
    company_files: list[UploadFile] = File(...),
    specification_files: list[UploadFile] = File(...),
) -> dict:

    try:
        company_payloads: list[
            tuple[str, bytes]
        ] = []

        for uploaded_file in company_files:

            content = (
                await uploaded_file.read()
            )

            company_payloads.append(
                (
                    uploaded_file.filename
                    or "company_file",
                    content,
                )
            )


        specification_payloads: list[
            tuple[str, bytes]
        ] = []

        for uploaded_file in specification_files:

            content = (
                await uploaded_file.read()
            )

            specification_payloads.append(
                (
                    uploaded_file.filename
                    or "specification_file",
                    content,
                )
            )


        return compare_documents(
            company_files=(
                company_payloads
            ),
            specification_files=(
                specification_payloads
            ),
        )


    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        ) from error


# ISTLINK_CANONICAL_SOURCE_PDF_V1
# The PDF is served only if its path is catalog-backed and inside an
# administrator-configured local storage root. Never accept a filesystem path
# from the browser.
@app.get('/sources/{version_id}/clauses/{clause_id}/pdf')
def source_clause_pdf(version_id: str, clause_id: str):
    import os
    from pathlib import Path, PurePosixPath
    from fastapi.responses import Response

    record = get_source_clause(version_id=version_id, clause_id=clause_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Clause bulunamadı.')
    if hasattr(record, 'model_dump'):
        record = record.model_dump()
    if not isinstance(record, dict):
        raise HTTPException(status_code=502, detail='Kaynak kaydı geçersiz.')

    local_ref = str(record.get('local_path') or '').replace('\\', '/')
    local_part = PurePosixPath(local_ref)
    if (
        not local_ref.lower().endswith('.pdf')
        or not local_ref
        or local_part.is_absolute()
        or '..' in local_part.parts
        or ':' in local_ref
    ):
        raise HTTPException(status_code=404, detail='PDF kaynağı bulunamadı.')

    roots = os.getenv('PARADOKS_PDF_ROOTS', '')
    for raw_root in roots.split(';'):
        if not raw_root.strip():
            continue
        root = Path(raw_root.strip()).expanduser().resolve()
        if not root.is_dir():
            continue
        # Prefer canonical relative location; the basename fallback supports
        # verified legacy parser copies without exposing arbitrary paths.
        for candidate in (root.joinpath(*local_part.parts), root / local_part.name):
            actual = candidate.resolve()
            if actual.is_relative_to(root) and actual.is_file():
                # ISTLINK_CLAUSE_PAGES_ONLY_V1: preserve PDF figures/tables,
                # but send only the pages authorized by this catalog clause.
                from app.services.source_pdf_pages import extract_clause_pdf_pages
                try:
                    pages_pdf = extract_clause_pdf_pages(
                        actual,
                        record.get('page_start'),
                        record.get('page_end'),
                    )
                except (ValueError, RuntimeError, OSError) as exc:
                    raise HTTPException(
                        status_code=422,
                        detail='Kaynak PDF sayfa aralığı okunamadı.',
                    ) from exc
                return Response(
                    content=pages_pdf,
                    media_type='application/pdf',
                    headers={
                        'Content-Disposition': 'inline; filename="clause-pages.pdf"',
                        'X-Content-Type-Options': 'nosniff',
                        'Cache-Control': 'private, no-store',
                    },
                )
    raise HTTPException(status_code=404, detail='Yerel PDF bulunamadı.')
