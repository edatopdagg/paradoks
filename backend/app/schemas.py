from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class PlannedQuestionResponse(BaseModel):
    text: str
    intent: str
    answered: bool = False


class Source(BaseModel):
    org: str
    code: str
    version: str
    clause: str
    clause_title: str
    status: str
    source_url: str
    distance: float

    source_id: str = ""
    document_id: str = ""
    page_number: int | None = None
    viewer_url: str = ""
    highlight_text: str = ""


class BlockedSource(BaseModel):
    org: str
    code: str
    source_url: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source]
    blocked_sources: list[BlockedSource]

    conversation_id: str | None = None
    detected_language: Literal["tr", "en"] = "tr"

    questions: list[
        PlannedQuestionResponse
    ] = Field(
        default_factory=list
    )

    standard_answer: str = ""
    assistant_answer: str = ""