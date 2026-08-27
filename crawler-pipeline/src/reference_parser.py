"""
Parses raw reference lines from standard documents into structured {org, code, title} objects.

Examples of lines this parser can handle:
    [2]  3GPP TS 22.003: "Circuit Teleservices..."
    [12] ITU-T Recommendation X.210: "..."
    [25] GSMA AD.26: "Coding of Cell Broadcast Functions"
    [32] ETSI TS 102 900: "..."
    [33] IETF RFC 4960: "Stream Control Transmission Protocol"
    [47] ATIS-0700041: "WEA 3.0: Device-Based Geo-Fencing"

Note: Source files (especially DOCX and PDF) frequently use non-breaking spaces (\\xa0) 
or zero-width spaces instead of normal spaces between tokens[cite: 2]. 
The normalize_whitespace() function mitigates this encoding issue[cite: 2].
"""

import re
from typing import Optional

from models import Reference

PATTERNS: dict[str, re.Pattern] = {
    "3GPP":  re.compile(r"3GPP\s+(TS|TR)\s*(\d{2}\.\d{3})(?:\s+Version\s+[\d.]+)?", re.IGNORECASE),
    "ETSI":  re.compile(r"ETSI\s+(TS|EN|TR)\s*(\d{3}\s?\d{3})", re.IGNORECASE),
    "IETF":  re.compile(r"(?:IETF\s+)?RFC\s*(\d{3,5})", re.IGNORECASE),
    "ITU-T": re.compile(r"ITU-T\s+Rec(?:ommendation)?\.?\s*([A-Z]\.\d+)", re.IGNORECASE),
    "ATIS":  re.compile(r"ATIS-(\d{7}(?:\.v\d{3})?)", re.IGNORECASE),
    "GSMA":  re.compile(r"\bGSMA\s+([A-Z]{2}\.\d{1,3})\b"),
    "IEEE":  re.compile(r"IEEE\s+(\d{2,4}(?:\.\d+[a-z]?)?)", re.IGNORECASE),
    "O-RAN": re.compile(r"O-RAN\.[A-Z0-9\-]+", re.IGNORECASE),
    "BBF":   re.compile(r"(?:BBF|TR)-\d{3}", re.IGNORECASE),
    "MEF":   re.compile(r"MEF\s+(\d{1,3})", re.IGNORECASE),
}

# Regex to capture the reference number (e.g., "[2]") and the rest of the line[cite: 2]
REF_LINE = re.compile(r"^\[(\d+)\]\s*(.+)$")

# Regex to capture the document title enclosed in double quotes[cite: 2]
TITLE = re.compile(r'[""\"]([^""\"]+)[""\"]')


def normalize_whitespace(text: str) -> str:
    """
    Cleans up hidden, non-breaking, or zero-width characters caused by document formatting[cite: 2].
    Converts them into standard spaces for accurate regex matching.
    """
    return text.replace("\xa0", " ").replace("\u200b", "")


def _extract_code(org: str, match: re.Match) -> str:
    """
    Formats the extracted regex groups into a clean, standardized document code based on the organization[cite: 2].
    """
    groups = match.groups()
    
    # 3GPP and ETSI require the prefix (e.g., "TS") alongside the number[cite: 2]
    if org in ("3GPP", "ETSI"):
        return f"{groups[0].upper()} {groups[1]}"
        
    # Other organizations just return the exact captured identifier[cite: 2]
    if org in ("IETF", "ITU-T", "ATIS", "GSMA"):
        return groups[0]
        
    return match.group(0)


def parse_reference_line(line: str) -> Optional[Reference]:
    """
    Takes a single line of text from the references section, cleans it, and attempts to extract
    the organization, document code, and title.
    Returns a Reference object if successful, or None if it's invalid or marked as 'void'[cite: 2].
    """
    line = normalize_whitespace(line).strip()
    m = REF_LINE.match(line)
    
    if not m:
        return None

    ref_number = int(m.group(1))
    body = m.group(2).strip()

    # If a document is deprecated or cancelled, it is usually marked as "Void"[cite: 2].
    # We skip these to avoid dead ends in our crawling queue[cite: 2].
    if body.lower().startswith("void"):
        return None  

    # Check the cleaned line against all known organization patterns[cite: 2]
    for org, pattern in PATTERNS.items():
        match = pattern.search(body)
        if not match:
            continue
            
        code = _extract_code(org, match)
        
        # Attempt to find a quoted title, default to empty string if not found[cite: 2]
        title_match = TITLE.search(body)
        title = title_match.group(1) if title_match else ""
        
        return Reference(raw_text=line, org=org, code=code, title=title, ref_number=ref_number)

    # If the line structure doesn't match any known organization format, ignore it.
    # Note: A new pattern must be added to the PATTERNS dictionary to support new orgs[cite: 2].
    return None


def parse_references_section(text: str) -> list[Reference]:
    """
    Main entry point for parsing. 
    Takes a large block of text (the entire references section), splits it by newlines, 
    and passes each line to the individual line parser[cite: 2].
    Returns a list of successfully identified Reference objects[cite: 2].
    """
    refs = []
    for raw_line in text.splitlines():
        ref = parse_reference_line(raw_line)
        if ref:
            refs.append(ref)
    return refs