"""Run the V3 reference parser against the three verified pilot documents."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from v3_reference_parser import parse_v3_references


SOURCES = (
    ("3GPP TS 23.040", "3GPP", "documents/3gpp/ts-23-040/*/extracted.txt"),
    ("IETF RFC 4960", "IETF", "documents/ietf/4960/*/extracted.txt"),
    ("ETSI TS 102 900", "ETSI", "documents/etsi/ts-102-900/*/extracted.txt"),
)


def _find_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"Bulunamadı: {root / pattern}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    args = parser.parse_args()
    input_dir = Path(args.input_dir).resolve()

    parsed_by_label = {}
    for label, org, pattern in SOURCES:
        text_path = _find_one(input_dir, pattern)
        text = text_path.read_text(encoding="utf-8")
        references = parse_v3_references(org, text)
        parsed_by_label[label] = references

        print("\n" + "=" * 72)
        print("DOCUMENT:", label)
        print("TEXT:", text_path)
        print("REFERENCE COUNT:", len(references))
        print("TARGET ORGANIZATIONS:", dict(Counter(ref.org for ref in references)))
        print("REFERENCE KINDS:", dict(Counter(ref.reference_kind for ref in references)))
        for reference in references[:20]:
            print(
                f"{reference.reference_kind} | "
                f"{reference.org} | {reference.code} | {reference.title}"
            )

    rfc_references = parsed_by_label["IETF RFC 4960"]
    if not rfc_references:
        raise RuntimeError("RFC 4960 referansları yine 0 çıktı.")
    if not any(ref.reference_kind == "normative" for ref in rfc_references):
        raise RuntimeError("RFC 4960 normative referansları bulunamadı.")
    if not any(ref.reference_kind == "informative" for ref in rfc_references):
        raise RuntimeError("RFC 4960 informative referansları bulunamadı.")

    etsi_targets = {
        (reference.org, reference.code)
        for reference in parsed_by_label["ETSI TS 102 900"]
    }
    if ("3GPP", "TS 23.041") not in etsi_targets:
        raise RuntimeError("ETSI TS 123 041 takma kimliği 3GPP TS 23.041'e çevrilmedi.")
    if ("ETSI", "TS 102 182") not in etsi_targets:
        raise RuntimeError("Gerçek ETSI TS 102 182 kimliği korunmadı.")

    print("\n" + "=" * 72)
    print("ALL REFERENCE PARSERS VERIFIED")


if __name__ == "__main__":
    main()
