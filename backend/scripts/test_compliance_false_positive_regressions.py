from app.services.compliance_service import (
    ExtractedRow,
    _aggregate_requirement_evidence,
    _atomic_capability_terms,
    _critical_values,
    _guard_semantic_only_fc,
)


def row(
    text: str,
    row_number: int = 1,
) -> ExtractedRow:
    return ExtractedRow(
        row_number=row_number,
        values={
            "text": text,
        },
        text=text,
        source_filename="regression.txt",
        source_page=None,
        source_kind="txt",
    )


# ============================================================
# 1. AVAILABILITY
# ============================================================

availability_requirement = (
    "\u00c7\u00f6z\u00fcm, %99,999 y\u00fcksek sistem "
    "eri\u015filebilirli\u011fini desteklemelidir."
)

availability_atoms = (
    _atomic_capability_terms(
        availability_requirement
    )
)

assert (
    "availability"
    in availability_atoms
), (
    "Availability atomu bulunamadi. "
    f"atoms={sorted(availability_atoms)}"
)

assert (
    "percent:99.999"
    in _critical_values(
        availability_requirement
    )
)


# ============================================================
# 2. MESSAGE SEGMENTATION
# ============================================================

segmentation_requirement = (
    "Uzun mesajlar i\u00e7in mesaj b\u00f6l\u00fcmleme "
    "(segmentation) desteklenmelidir."
)

segmentation_atoms = (
    _atomic_capability_terms(
        segmentation_requirement
    )
)

assert (
    "message_segmentation"
    in segmentation_atoms
), (
    "Message segmentation atomu bulunamadi. "
    f"atoms={sorted(segmentation_atoms)}"
)


# ============================================================
# 3. COMPOSITE REQUIREMENT
#    geo-site + testbed + VM
# ============================================================

composite_requirement = row(
    (
        "Teklif; 2 co\u011frafi saha (geo-site) "
        "kurulumu ve bir test ortam\u0131 (testbed) "
        "esas al\u0131narak haz\u0131rlanmal\u0131d\u0131r. "
        "VM boyutland\u0131rmas\u0131 sa\u011flanmal\u0131d\u0131r."
    )
)

company_rows = [
    row(
        (
            "Virtualization | VM Support | "
            "Fully Supported"
        ),
        1,
    ),
]

semantic_scores = [
    0.90,
]

scored_candidates = [
    (
        0.90,
        0,
        {},
    ),
]

aggregate = (
    _aggregate_requirement_evidence(
        requirement=composite_requirement,
        company_rows=company_rows,
        semantic_scores=semantic_scores,
        scored_candidates=scored_candidates,
    )
)

assert aggregate is not None

assert (
    aggregate["status"]
    == "PC"
), (
    "Yalnizca VM kaniti olan composite requirement "
    "PC olmaliydi. "
    f"actual={aggregate['status']}"
)

assert (
    "feature:geo_site"
    in aggregate["missing_signals"]
)

assert (
    "feature:testbed"
    in aggregate["missing_signals"]
)

assert (
    "feature:vm"
    in aggregate["fully_supported_signals"]
)




# ============================================================
# SEMANTIC-ONLY FC GUARD
# ============================================================

unstructured_requirement = (
    "Cozum uyari dogrulama mekanizmasini "
    "desteklemelidir."
)

assert (
    _atomic_capability_terms(
        unstructured_requirement
    )
    == set()
)

guarded_status = (
    _guard_semantic_only_fc(
        status="FC",
        requirement_kind="CAPABILITY",
        requirement_text=unstructured_requirement,
        aggregate=None,
    )
)

assert (
    guarded_status
    == "REVIEW"
), (
    "Atomsuz teknik requirement semantic-only FC "
    f"olmamaliydi. actual={guarded_status}"
)


structured_requirement = (
    "Sistem HTTP/2 desteklemelidir."
)

assert (
    "http2"
    in _atomic_capability_terms(
        structured_requirement
    )
)

structured_status = (
    _guard_semantic_only_fc(
        status="FC",
        requirement_kind="CAPABILITY",
        requirement_text=structured_requirement,
        aggregate=None,
    )
)

assert (
    structured_status
    == "FC"
), (
    "Atomu bilinen requirement gereksiz yere "
    f"dusuruldu. actual={structured_status}"
)


aggregate_status = (
    _guard_semantic_only_fc(
        status="FC",
        requirement_kind="CAPABILITY",
        requirement_text=unstructured_requirement,
        aggregate={
            "status": "FC",
        },
    )
)

assert (
    aggregate_status
    == "FC"
), (
    "Aggregate kaniti bulunan sonuc guard "
    "tarafindan dusuruldu."
)




# ============================================================
# PARTIAL COMPLIANCE REGRESSIONS
# ============================================================

partial_cases = [
    {
        "name": "backup_restore",
        "requirement": (
            "Sistem yedekleme ve geri y\u00fckleme "
            "desteklenmelidir."
        ),
        "evidence": (
            "Sistem ve uygulamaya ait t\u00fcm "
            "kay\u0131tlar saklanmal\u0131 ve "
            "yedeklenmelidir. Fully Supported"
        ),
        "missing": {
            "feature:restore",
        },
        "supported": {
            "feature:backup",
        },
    },
    {
        "name": "multi_technology",
        "requirement": (
            "Yay\u0131n, t\u00fcm teknolojiler i\u00e7in "
            "desteklenmelidir: CDMA, GSM, UMTS, LTE ve 5G."
        ),
        "evidence": (
            "2G, 3G, 4G LTE and 5G Support "
            "| Fully Supported"
        ),
        "missing": {
            "feature:tech_cdma",
        },
        "supported": {
            "feature:tech_gsm",
            "feature:tech_umts",
            "feature:tech_lte",
            "feature:tech_5g",
        },
    },
    {
        "name": "https_over_cap",
        "requirement": (
            "HTTPS \u00fczerinden CAP "
            "desteklenmelidir."
        ),
        "evidence": (
            "SSL kullan\u0131larak https "
            "protokol\u00fc ile eri\u015fim "
            "Fully Supported"
        ),
        "missing": {
            "feature:cap",
        },
        "supported": {
            "feature:https",
        },
    },
    {
        "name": "mutual_tls",
        "requirement": (
            "\u00c7\u00f6z\u00fcm, HTTPS tabanl\u0131 "
            "arabirimler i\u00e7in kar\u015f\u0131l\u0131kl\u0131 TLS "
            "(mutual TLS) kimlik do\u011frulamas\u0131n\u0131 "
            "desteklemelidir."
        ),
        "evidence": (
            "TLS kullan\u0131larak https "
            "protokol\u00fc ile eri\u015fim "
            "Fully Supported"
        ),
        "missing": {
            "feature:mutual_tls",
        },
        "supported": {
            "feature:tls",
            "feature:https",
        },
    },
    {
        "name": "languages",
        "requirement": (
            "\u00d6zbek\u00e7e, Rus\u00e7a, \u0130ngilizce "
            "ve Karakalpak\u00e7a dilleri "
            "desteklenmelidir."
        ),
        "evidence": (
            "English, German, Russian, Arabic, "
            "Spanish, French languages support "
            "| Fully Supported"
        ),
        "missing": {
            "feature:lang_uzbek",
            "feature:lang_karakalpak",
        },
        "supported": {
            "feature:lang_english",
            "feature:lang_russian",
        },
    },
]


for case in partial_cases:

    requirement_row = row(
        case["requirement"],
        1,
    )

    company_rows = [
        row(
            case["evidence"],
            1,
        ),
    ]

    aggregate = (
        _aggregate_requirement_evidence(
            requirement=requirement_row,
            company_rows=company_rows,
            semantic_scores=[
                0.90,
            ],
            scored_candidates=[
                (
                    0.90,
                    0,
                    {},
                ),
            ],
        )
    )

    assert aggregate is not None

    assert (
        aggregate["status"]
        == "PC"
    ), (
        f"{case['name']} PC olmaliydi. "
        f"actual={aggregate['status']}"
    )

    assert case["missing"].issubset(
        set(
            aggregate[
                "missing_signals"
            ]
        )
    ), (
        f"{case['name']} missing signals hatali. "
        f"actual={aggregate['missing_signals']}"
    )

    assert case["supported"].issubset(
        set(
            aggregate[
                "fully_supported_signals"
            ]
        )
    ), (
        f"{case['name']} supported signals hatali. "
        f"actual={aggregate['fully_supported_signals']}"
    )


print(
    "COMPLIANCE FALSE POSITIVE REGRESSIONS: PASS"
)
