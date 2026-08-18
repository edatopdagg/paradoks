from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Source(BaseModel):
    org: str
    code: str
    version: str
    clause: str
    clause_title: str
    status: str
    source_url: str
    distance: float


class BlockedSource(BaseModel):
    org: str
    code: str
    source_url: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source]
    blocked_sources: list[BlockedSource]