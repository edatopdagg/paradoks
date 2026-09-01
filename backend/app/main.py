from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    ChatRequest,
    ChatResponse,
    SourceClauseResponse,
)
from app.services.chat_orchestrator import (
    generate_chat_response,
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
    conversation_id=request.conversation_id,
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
