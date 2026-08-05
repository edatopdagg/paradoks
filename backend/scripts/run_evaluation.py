import json
from pathlib import Path
from typing import Any

from app.services.chat_service import generate_reply


BASE_DIR = Path(__file__).resolve().parent.parent
EVALUATION_FILE = BASE_DIR / "data" / "evaluation_cases.json"


def normalize_text(text: str) -> str:
    """
    Büyük-küçük harf ve gereksiz boşluk farklarını kaldırır.
    """
    return " ".join(text.casefold().split())


def load_evaluation_cases() -> list[dict[str, Any]]:
    with EVALUATION_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_expected_source(
    sources: list[dict[str, Any]],
    expected_document: str | None,
    expected_clause: str | None,
) -> bool:
    """
    Beklenen belge ve maddenin API kaynakları içinde bulunup
    bulunmadığını kontrol eder.
    """
    if expected_document is None and expected_clause is None:
        return len(sources) == 0

    return any(
        source.get("code") == expected_document
        and source.get("clause") == expected_clause
        for source in sources
    )


def check_required_fact_groups(
    reply: str,
    required_fact_groups: list[list[str]],
) -> tuple[bool, list[list[str]]]:
    """
    Her teknik gerçek için tanımlanan alternatif ifadelerden
    en az birinin cevapta bulunup bulunmadığını kontrol eder.
    """
    normalized_reply = normalize_text(reply)
    missing_groups: list[list[str]] = []

    for phrase_group in required_fact_groups:
        group_matched = any(
            normalize_text(phrase) in normalized_reply
            for phrase in phrase_group
        )

        if not group_matched:
            missing_groups.append(phrase_group)

    return len(missing_groups) == 0, missing_groups

def check_forbidden_claim_groups(
    reply: str,
    forbidden_claim_groups: list[list[str]],
) -> tuple[bool, list[str]]:
    """
    Yasaklanan her iddianın farklı söylenişlerini kontrol eder.
    Gruplardaki ifadelerden herhangi biri cevapta geçerse
    ilgili yanlış iddia tespit edilmiş sayılır.
    """
    normalized_reply = normalize_text(reply)
    detected_claims: list[str] = []

    for phrase_group in forbidden_claim_groups:
        for phrase in phrase_group:
            if normalize_text(phrase) in normalized_reply:
                detected_claims.append(phrase)
                break

    return len(detected_claims) == 0, detected_claims


def check_abstention(
    reply: str,
    sources: list[dict[str, Any]],
    should_abstain: bool,
) -> bool:
    """
    Kaynak bulunmayan sorularda sistemin cevap üretmekten
    kaçınıp kaçınmadığını kontrol eder.
    """
    normalized_reply = normalize_text(reply)

    abstention_detected = (
        not sources
        and "bulunamad" in normalized_reply
    )

    if should_abstain:
        return abstention_detected

    return not abstention_detected


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = generate_reply(case["question"])

    reply = result["reply"]
    sources = result["sources"]

    source_ok = check_expected_source(
        sources=sources,
        expected_document=case["expected_document"],
        expected_clause=case["expected_clause"],
    )

    required_facts_ok, missing_fact_groups = check_required_fact_groups(
        reply=reply,
        required_fact_groups=case["required_fact_groups"],
    )
    forbidden_claims_ok, detected_claims = check_forbidden_claim_groups(
        reply=reply,
        forbidden_claim_groups=case["forbidden_claim_groups"],
    )

    abstention_ok = check_abstention(
        reply=reply,
        sources=sources,
        should_abstain=case["should_abstain"],
    )

    passed = all(
        [
            source_ok,
            required_facts_ok,
            forbidden_claims_ok,
            abstention_ok,
        ]
    )

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "reply": reply,
        "source_ok": source_ok,
        "required_facts_ok": required_facts_ok,
        "missing_facts_groups": missing_facts_groups,
        "forbidden_claims_ok": forbidden_claims_ok,
        "detected_forbidden_claims": detected_claims,
        "abstention_ok": abstention_ok,
        "passed": passed,
        "sources": sources,
    }


def print_case_result(result: dict[str, Any]) -> None:
    status = "BAŞARILI" if result["passed"] else "BAŞARISIZ"

    print("\n" + "=" * 70)
    print(f"Test: {result['id']}")
    print(f"Kategori: {result['category']}")
    print(f"Durum: {status}")
    print(f"Soru: {result['question']}")
    print(f"Cevap: {result['reply']}")
    print("-" * 70)
    print(f"Doğru kaynak/madde: {result['source_ok']}")
    print(f"Gerekli bilgiler mevcut: {result['required_facts_ok']}")
    print(f"Yasaklı iddia yok: {result['forbidden_claims_ok']}")
    print(f"Kaçınma davranışı doğru: {result['abstention_ok']}")

    if result["missing_fact_groups"]:
        print("Eksik bilgi grupları:")

        for phrase_group in result["missing_fact_groups"]:
            print(
                "  - Şunlardan en az biri bekleniyordu: "
                + " / ".join(phrase_group)
            )

    if result["detected_forbidden_claims"]:
        print(
            "Tespit edilen yasaklı ifadeler: "
            + ", ".join(result["detected_forbidden_claims"])
        )


def main() -> None:
    cases = load_evaluation_cases()
    results: list[dict[str, Any]] = []

    for case in cases:
        result = evaluate_case(case)
        results.append(result)
        print_case_result(result)

    passed_count = sum(
        result["passed"] for result in results
    )

    total_count = len(results)
    success_rate = (
        passed_count / total_count * 100
        if total_count
        else 0
    )

    print("\n" + "=" * 70)
    print("GENEL DEĞERLENDİRME")
    print(f"Toplam test: {total_count}")
    print(f"Başarılı test: {passed_count}")
    print(f"Başarısız test: {total_count - passed_count}")
    print(f"Başarı oranı: %{success_rate:.1f}")


if __name__ == "__main__":
    main()