"""
Shared schema between Person A (crawler) and Person B (RAG)[cite: 7]. 
Don't change field names/types without syncing with the other team member[cite: 7].
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DocStatus(str, Enum):
    """Enumeration representing the resolution and processing status of a document[cite: 7]."""
    PENDING = "pending"         # Successfully found, waiting to be fetched/processed
    INDEXED = "indexed"         # Successfully chunked and written to the database
    BLOCKED = "blocked"         # Paywalled or inaccessible; only the link is kept[cite: 7]
    VOID = "void"               # Marked as "Void" (deprecated/cancelled) in the source document[cite: 7]
    UNRESOLVED = "unresolved"   # The resolver chain could not find any valid URL[cite: 7]


@dataclass
class Reference:
    """Represents a raw reference extracted from the document text[cite: 7]."""
    raw_text: str
    org: str            # e.g., "3GPP", "IETF", "ATIS", "ETSI", "ITU-T", "GSMA"[cite: 7]
    code: str           # e.g., "TS 23.041", "RFC 4960", "AD.26"[cite: 7]
    title: str
    ref_number: Optional[int] = None


@dataclass
class ResolvedSource:
    """Represents a reference that has been processed by the resolver[cite: 7]."""
    reference: Reference
    status: DocStatus
    source_url: Optional[str] = None
    version: Optional[str] = None
    local_path: Optional[str] = None


@dataclass
class Chunk:
    """
    Represents a specific, isolated section of a document (e.g., a single clause),
    ready to be embedded and indexed in the Vector Database[cite: 7].
    """
    text: str
    doc_org: str
    doc_code: str
    version: str
    clause: str
    clause_title: str
    status: DocStatus
    source_url: Optional[str] = None
    # The mathematical vector representation of the text. Excluded from string representation[cite: 7].
    embedding: Optional[list[float]] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Converts the dataclass into a dictionary format suitable for database metadata insertion[cite: 7]."""
        return {
            "text": self.text,
            "doc_org": self.doc_org,
            "doc_code": self.doc_code,
            "version": self.version,
            "clause": self.clause,
            "clause_title": self.clause_title,
            "status": self.status.value if isinstance(self.status, DocStatus) else self.status,
            "source_url": self.source_url,
        }