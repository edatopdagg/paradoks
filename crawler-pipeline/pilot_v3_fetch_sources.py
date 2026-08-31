import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from models import Reference
from resolver import resolve
from v3_fetcher import fetch_document


REFERENCES = (
    Reference(
        raw_text="",
        org="3GPP",
        code="TS 23.040",
        title="Technical realization of the Short Message Service (SMS)",
    ),
    Reference(
        raw_text="",
        org="IETF",
        code="4960",
        title="Stream Control Transmission Protocol",
    ),
    Reference(
        raw_text="",
        org="ETSI",
        code="TS 102 900",
        title="European Public Warning System (EU-ALERT)",
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    failures: list[str] = []

    for reference in REFERENCES:
        label = f"{reference.org} {reference.code}"
        print("\n" + "=" * 70)
        print("FETCH:", label)
        try:
            resolved = resolve(reference)
            if not resolved.source_url:
                raise RuntimeError(f"Kaynak URL bulunamadı: {resolved.status}")

            fetched = fetch_document(
                org=reference.org,
                code=reference.code,
                title=reference.title,
                source_url=resolved.source_url,
                output_root=output_dir,
            )
            print("STATUS: VERIFIED")
            print("VERSION:", fetched.version)
            print("RELEASE:", fetched.release)
            print("SOURCE:", fetched.source_url)
            print("LOCAL:", fetched.local_path)
            print("PACKAGE:", fetched.package_path)
            print("TEXT:", len(fetched.document_text), "characters")
            print("PAGES:", len(fetched.page_texts))
            print("SHA256:", fetched.content_sha256)
            print("HEAD:", fetched.document_text[:300].replace("\n", " | "))
        except Exception as error:
            failures.append(label)
            print("STATUS: FAILED")
            print("ERROR:", type(error).__name__, str(error))

    print("\n" + "=" * 70)
    if failures:
        print("FAILED:", ", ".join(failures))
        raise SystemExit(1)
    print("ALL SOURCES VERIFIED")


if __name__ == "__main__":
    main()
