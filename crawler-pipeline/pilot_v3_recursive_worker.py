import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(
    0,
    str(BASE_DIR / "src"),
)

from v3_recursive_worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--catalog",
        required=True,
    )

    parser.add_argument(
        "--data-root",
        required=True,
    )

    parser.add_argument(
        "--max-documents",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--max-depth",
        type=int,
    )

    parser.add_argument(
        "--org",
        action="append",
        dest="organizations",
    )

    args = parser.parse_args()

    organizations = (
        tuple(args.organizations)
        if args.organizations
        else None
    )

    summary = run_worker(
        catalog_path=args.catalog,
        data_root=args.data_root,
        max_documents=args.max_documents,
        max_depth=args.max_depth,
        organizations=organizations,
    )

    print(
        "\nWORKER SUMMARY:",
        summary,
    )


if __name__ == "__main__":
    main()