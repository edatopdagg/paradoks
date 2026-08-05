from fastapi import FastAPI

from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import generate_reply


app = FastAPI()


@app.get("/")
def root():
    return {
        "message": "Paradoks API çalışıyor"
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest) -> ChatResponse:
    result = generate_reply(request.message)

    return ChatResponse(**result)