import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
EVALUATION_FILE = BASE_DIR / "data" / "evaluation_cases.json"

REQUIRED_FIELDS = {
    "id",
    "category",
    "question",
    "expected_document",
    "expected_clause",
    "required_fact_groups",
    "forbidden_claim_groups",
    "should_abstain",
}


def load_evaluation_cases() -> list[dict[str, Any]]:
    with EVALUATION_FILE.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise TypeError(
            "evaluation_cases.json dosyasının kök değeri liste olmalıdır."
        )

    return cases


def validate_phrase_groups(
    groups: Any,
    field_name: str,
    case_id: str,
) -> None:
    if not isinstance(groups, list):
        raise TypeError(
            f"{case_id} için {field_name} liste olmalıdır."
        )

    for group_index, group in enumerate(groups, start=1):
        if not isinstance(group, list):
            raise TypeError(
                f"{case_id} içindeki {field_name} alanının "
                f"{group_index}. grubu liste olmalıdır."
            )

        if not group:
            raise ValueError(
                f"{case_id} içindeki {field_name} alanının "
                f"{group_index}. grubu boş olamaz."
            )

        if not all(
            isinstance(phrase, str) and phrase.strip()
            for phrase in group
        ):
            raise TypeError(
                f"{case_id} içindeki {field_name} alanının "
                f"{group_index}. grubunda yalnızca boş olmayan "
                "metinler bulunmalıdır."
            )


def validate_case(case: dict[str, Any], index: int) -> None:
    missing_fields = REQUIRED_FIELDS - case.keys()

    if missing_fields:
        raise ValueError(
            f"{index}. test kaydında eksik alanlar var: "
            f"{sorted(missing_fields)}"
        )

    case_id = case["id"]

    if not isinstance(case_id, str) or not case_id.strip():
        raise TypeError(
            f"{index}. test kaydının id alanı boş olmayan metin olmalıdır."
        )

    if not isinstance(case["question"], str) or not case["question"].strip():
        raise TypeError(
            f"{case_id} için question boş olmayan metin olmalıdır."
        )

    validate_phrase_groups(
        groups=case["required_fact_groups"],
        field_name="required_fact_groups",
        case_id=case_id,
    )

    validate_phrase_groups(
        groups=case["forbidden_claim_groups"],
        field_name="forbidden_claim_groups",
        case_id=case_id,
    )

    if not isinstance(case["should_abstain"], bool):
        raise TypeError(
            f"{case_id} için should_abstain true veya false olmalıdır."
        )


def main() -> None:
    cases = load_evaluation_cases()

    for index, case in enumerate(cases, start=1):
        validate_case(case, index)

    categories = sorted(
        {case["category"] for case in cases}
    )

    print(f"Değerlendirme dosyası: {EVALUATION_FILE}")
    print(f"Toplam test sayısı: {len(cases)}")
    print(f"Kategoriler: {', '.join(categories)}")
    print("Tüm değerlendirme kayıtları geçerli.")


if __name__ == "__main__":
    main()