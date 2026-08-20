from pathlib import Path
import sys
import time


BACKEND_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BACKEND_DIR),
)

from app.services.reranker_service import Reranker


QUERY = (
    "telefon şebekeden kendi kendine çıkış yapıyorsa "
    "bunun prosedürü neydi?"
)


BASE_TEXTS = [
    """
    The deregistration procedure is used to deregister a UE from
    the 5GS. Deregistration may be initiated by the UE or by the
    network. The procedure releases registration related resources
    and updates the registration management state. The AMF may
    initiate network triggered deregistration under conditions
    specified by the system procedures.
    """,

    """
    A UE performs the Registration procedure in order to register
    with the 5GS. Registration Management is used to register or
    deregister a UE and establish the registration context between
    the UE and the network. Registration procedures include initial
    registration, mobility registration update and periodic
    registration update.
    """,

    """
    The Service Request procedure is used by a UE in CM-IDLE state
    to establish a secure signalling connection to the AMF and
    request activation of user plane resources when required.
    The network may also trigger procedures related to UE
    reachability and pending downlink data.
    """,

    """
    Radio link failure handling is performed when the UE detects
    that the radio connection can no longer be maintained.
    Depending on radio conditions and configuration, the UE may
    perform RRC re-establishment, cell selection or other recovery
    procedures.
    """,

    """
    PDU Session Establishment allows a UE to request establishment
    of a PDU Session toward a data network. The procedure involves
    the AMF, SMF and UPF and results in establishment of session
    management context and user plane resources.
    """,

    """
    Handover procedures support mobility of a UE between cells
    while maintaining service continuity. Depending on the radio
    access technology and architecture, source and target nodes
    exchange signalling and transfer UE context.
    """,
]


def make_candidate(
    index: int,
    text: str,
) -> dict:
    expanded_text = (
        (text.strip() + "\n") * 8
    ).strip()

    return {
        "chunk_id": f"test_{index}",
        "text": expanded_text,
        "metadata": {
            "org": "3GPP",
            "code": "TEST",
            "clause": str(index),
        },
        "distance": 0.30 + (
            index * 0.01
        ),
    }


CANDIDATES = [
    make_candidate(
        index,
        text,
    )
    for index, text in enumerate(
        BASE_TEXTS,
        start=1,
    )
]


print()
print("=" * 70)
print("PARADOKS RERANKER PERFORMANCE TEST")
print("=" * 70)


# ---------------------------------------------------------
# MODEL LOAD
# ---------------------------------------------------------

load_start = time.perf_counter()

reranker = Reranker()

load_time = (
    time.perf_counter()
    - load_start
)

print(
    f"Model yükleme: {load_time:.2f} sn"
)


# ---------------------------------------------------------
# WARMUP
# ---------------------------------------------------------

print()
print("Warmup başlıyor...")

warmup_start = time.perf_counter()

reranker.rerank(
    query=QUERY,
    candidates=CANDIDATES[:2],
)

warmup_time = (
    time.perf_counter()
    - warmup_start
)

print(
    f"Warmup: {warmup_time:.2f} sn"
)


# ---------------------------------------------------------
# ADAY SAYISI TESTLERİ
# ---------------------------------------------------------

print()
print("-" * 70)

candidate_counts = [
    1,
    2,
    3,
    6,
]

print(
    "DEBUG candidate_counts:",
    repr(candidate_counts),
    "| len:",
    len(candidate_counts),
    flush=True,
)

for candidate_count in candidate_counts:
    print(
        "DEBUG LOOP GİRDİ:",
        candidate_count,
        flush=True,
    )

for candidate_count in candidate_counts:

    candidates = CANDIDATES[
        :candidate_count
    ]

    print(
        f"{candidate_count} aday testi başlıyor..."
    )

    start = time.perf_counter()

    result = reranker.rerank(
        query=QUERY,
        candidates=candidates,
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        f"{candidate_count} aday -> "
        f"{elapsed:.4f} sn | "
        f"dönen: {len(result)}"
    )


print("-" * 70)

print()
print("RERANKER TESTİ TAMAMLANDI")
print("=" * 70)