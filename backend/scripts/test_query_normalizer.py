from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BACKEND_DIR),
)

from app.services.query_normalizer import QueryNormalizer


normalizer = QueryNormalizer()


TEST_QUERIES = [
    "telefon şebekeden kendi kendine çıkış yapıyorsa bunun prosedürü neydi?",
    "UE şebekeden düşüyor neden olabilir",
    "registration request ne işe yarıyordu?",
    "telefon tekrar şebekeye kayıt olurken ne gönderiyor?",
    "service request ne zaman atılıyor?",
    "internet oturumu nasıl açılıyor?",
    "PDU session nasıl kapatılıyor?",
    "telefon hücre değiştirirken hangi prosedür çalışıyor?",
    "acil uyarı mesajları nasıl geliyor?",
    "kimlik doğrulama nasıl yapılıyor?",
    "operatör seçimi nasıl oluyor?",
    "roamingde hangi prosedür var?",
    "acil çağrıda kayıt işlemi nasıl oluyor?",
    "AMF UE context transfer nasıl çalışıyor?",
]


print()
print("=" * 80)
print("PARADOKS QUERY NORMALIZER TEST")
print("=" * 80)

for index, query in enumerate(
    TEST_QUERIES,
    start=1,
):
    variants = normalizer.normalize(
        query
    )

    print()
    print(f"{index}. SORU:")
    print(query)

    print("VARYANTLAR:")

    for variant_index, variant in enumerate(
        variants,
        start=1,
    ):
        print(
            f"   {variant_index}. {variant}"
        )

    print("-" * 80)


# ---------------------------------------------------------
# TEMEL DOĞRULAMALAR
# ---------------------------------------------------------

deregistration_test = normalizer.normalize(
    "telefon şebekeden kendi kendine çıkış yapıyorsa bunun prosedürü neydi?"
)

assert (
    deregistration_test[0]
    == "telefon şebekeden kendi kendine çıkış yapıyorsa bunun prosedürü neydi?"
)

assert (
    "UE deregistration procedure"
    in deregistration_test
)

registration_test = normalizer.normalize(
    "telefon tekrar şebekeye kayıt olurken ne gönderiyor?"
)

assert (
    "5GS registration procedure"
    in registration_test
)

unknown_test = normalizer.normalize(
    "AMF UE context transfer nasıl çalışıyor?"
)

assert unknown_test == [
    "AMF UE context transfer nasıl çalışıyor?"
]

release_test = normalizer.normalize(
    "PDU session nasıl kapatılıyor?"
)

assert (
    "PDU Session Release"
    in release_test
)

assert (
    "PDU Session Establishment"
    not in release_test
)

roaming_test = normalizer.normalize(
    "roamingde hangi prosedür var?"
)

assert (
    "roaming procedure"
    in roaming_test
)

emergency_test = normalizer.normalize(
    "acil çağrıda kayıt işlemi nasıl oluyor?"
)

assert (
    "emergency registration"
    in emergency_test
)

print()
print("=" * 80)
print("TÜM TEMEL TESTLER BAŞARILI")
print("=" * 80)