from app.services.compliance_service import (
    _atomic_capability_terms,
    _requirement_kind,
    _information_requires_explicit_value,
)


def expect_has(text: str, *signals: str) -> None:
    found = _atomic_capability_terms(text)
    missing = [signal for signal in signals if signal not in found]
    assert not missing, (text, found, missing)


def expect_not(text: str, *signals: str) -> None:
    found = _atomic_capability_terms(text)
    bad = [signal for signal in signals if signal in found]
    assert not bad, (text, found, bad)


# 27 - warning source integration
expect_has(
    "Birden fazla uyarı kaynağıyla entegrasyon desteklenmelidir.",
    "warning_source_integration",
)
expect_has(
    "Integration with other public alerting systems. AFAD etc.",
    "warning_source_integration",
)

# 36/37 - targeting
expect_has(
    "Bölgelere göre hedefleme desteklenmelidir.",
    "region_targeting",
)
expect_has(
    "Province, district, selected map area, cell and whole Turkey selection",
    "region_targeting",
    "target_cell",
)
expect_has(
    "Hücre, sektör, TA, ECGI, CGI bazında hedefleme desteklenmelidir.",
    "target_sector",
    "tracking_area",
    "ecgi",
    "target_cgi",
)

# 85 - AMF entegrasyonunun kısmi kanıtı
expect_has(
    "AMF ile entegrasyon için N50 arabirimini desteklemelidir.",
    "amf_integration",
    "n50",
)
expect_has(
    "The 4G-CBC and 5G-CBC (MME & AMF) interfaces",
    "amf_integration",
)

# 92 - negatif koşul AD desteği sayılmamalı
expect_not(
    "Active Directory ile entegrasyon mümkün değilse kullanıcı adı/şifre doğrulaması yapılabilir.",
    "active_directory",
    "central_directory",
)
expect_has(
    "Interface/application level user authentication should be possible via AD/LDAP.",
    "active_directory",
    "ldap",
    "central_directory",
)

# 93 - SIEM var, syslog ayrıca doğrulanmalı
expect_has(
    "They should work in compliance with a Turkcell SIEM system.",
    "siem_integration",
)

# 113 - bilgi/değer talebi
expect_has(
    "Hücre Yayını mesajlarının iletim süresini belirtmelidir.",
    "message_delivery_delay",
)
expect_has(
    "Message sending delay (From CBC to RN nodes) ?",
    "message_delivery_delay",
)
assert _requirement_kind(
    "Tedarikçi, Hücre Yayını mesajlarının iletim süresini belirtmelidir."
) == "INFO"
assert _information_requires_explicit_value(
    "Tedarikçi, Hücre Yayını mesajlarının iletim süresini belirtmelidir."
)

# Dokümantasyon maddeleri NC olmamalı; INFO olarak sınıflanmalı.
assert _requirement_kind(
    "Tedarikçi, sistem mimarisi ve kullanım senaryolarına ilişkin bir açıklama sunmalıdır."
) == "INFO"
assert _requirement_kind(
    "Lütfen CBC çözümünün uyumlu olduğu tüm standartları listeleyiniz."
) == "INFO"

# ------------------------------------------------------------
# Son ger?ek Excel regression ?rnekleri
# ------------------------------------------------------------

# Madde 8:
# "T?m bile?enler listelenmeli/a??klanmal?" teknik NC de?ildir.
assert _requirement_kind(
    "??z?me dahil olan t?m bile?enler "
    "Tedarik?i taraf?ndan listelenmeli ve a??klanmal?d?r."
) == "INFO"

# Madde 93:
# SIEM kan?t?, Syslog ?art?n?n yaln?z bir b?l?m?n? kar??lar.
expect_has(
    "??z?m, g?nl?kleri harici g?nl?k y?netimi ve "
    "SIEM sistemlerine iletmek i?in Syslog'u desteklemelidir.",
    "siem_integration",
    "syslog",
)

expect_has(
    "They should work in compliance with "
    "a Turkcell SIEM system.",
    "siem_integration",
)

# Madde 113:
# Kaynak ?zellik dosyas?ndaki ger?ek yaz?m hatas? da tan?nmal?.
expect_has(
    "Special Requirements | "
    "5.7.1.Mesagge sending delay "
    "(From CBC to RN nodes) ? | Fully Supported",
    "message_delivery_delay",
)


# ------------------------------------------------------------
# Audit cleanup regression ?rnekleri
# ------------------------------------------------------------

# Uzbekistan ?lke ad?d?r; Uzbek language de?ildir.
expect_not(
    "Tedarik?i, Beeline Uzbekistan ?ebekesinde "
    "Kamu Uyar?s? uygulamal?d?r.",
    "lang_uzbek",
)

# Ger?ek ?zbek?e dil gereksinimi yine yakalanmal?d?r.
expect_has(
    "Uzbek language support should be available.",
    "lang_uzbek",
)

# Kaynak Excel'deki expiration ?zelli?i mesaj expiration
# ?art?n? kar??layabilecek teknik kan?t ?retmelidir.
expect_has(
    "GUI Features | "
    "5.10.2.Phased and delayed effective times "
    "and expirations ? | Fully Supported",
    "message_expiration",
)

from app.services.compliance_service import (
    _select_display_evidence,
)

# REVIEW / NC i?in salt semantic benzerlik dayanak de?ildir.
_dummy_candidate = {
    "text": "Alakas?z semantic aday",
    "score": 0.91,
}

assert (
    _select_display_evidence(
        status="REVIEW",
        evidence_items=[],
        candidates=[_dummy_candidate],
    )
    is None
)

assert (
    _select_display_evidence(
        status="NC",
        evidence_items=[],
        candidates=[_dummy_candidate],
    )
    is None
)

# PC i?in semantic fallback halen kullan?labilir.
assert (
    _select_display_evidence(
        status="PC",
        evidence_items=[],
        candidates=[_dummy_candidate],
    )
    == _dummy_candidate
)


print("COMPLIANCE FINAL ROUND REGRESSIONS: PASS")
