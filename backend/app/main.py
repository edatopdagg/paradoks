from fastapi import FastAPI, File, HTTPException, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    ChatRequest,
    ChatResponse,
    SourceClauseResponse,
)
from app.services.chat_orchestrator import (
    generate_chat_response,
)
from app.services.compliance_service import compare_documents
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
    conversation_id=request.conversation_id,
    domain=request.domain,
)

    return ChatResponse(
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

        if not company_files:
            raise ValueError(
                "En az bir ?irket ?zellik dosyas? "
                "y?klemelisiniz."
            )

        if not specification_files:
            raise ValueError(
                "En az bir ?artname dosyas? "
                "y?klemelisiniz."
            )

        company_documents: list[
            tuple[str, bytes]
        ] = []

        for index, upload in enumerate(
            company_files,
            start=1,
        ):
            content = await upload.read()

            if not content:
                raise ValueError(
                    f"?irket dosyas? bo?: "
                    f"{upload.filename or index}"
                )

            company_documents.append(
                (
                    upload.filename
                    or f"company-{index}.txt",
                    content,
                )
            )

        specification_documents: list[
            tuple[str, bytes]
        ] = []

        for index, upload in enumerate(
            specification_files,
            start=1,
        ):
            content = await upload.read()

            if not content:
                raise ValueError(
                    f"?artname dosyas? bo?: "
                    f"{upload.filename or index}"
                )

            specification_documents.append(
                (
                    upload.filename
                    or f"specification-{index}.txt",
                    content,
                )
            )

        return compare_documents(
            company_files=(
                company_documents
            ),
            specification_files=(
                specification_documents
            ),
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
