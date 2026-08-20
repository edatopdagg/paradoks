import re


# ---------------------------------------------------------
# TELEKOM KAVRAM EŞLEŞMELERİ
# ---------------------------------------------------------
#
# Amaç:
# Kullanıcının günlük, eksik veya Türkçe ifadesini
# standartlarda geçmesi muhtemel teknik terimlerle
# desteklemek.
#
# Önemli:
# - Orijinal soru HER ZAMAN korunur.
# - Kullanıcının niyeti tek bir teknik kavrama zorlanmaz.
# - Fazla genel kurallar kullanılmaz.
# ---------------------------------------------------------

CONCEPT_RULES: list[
    tuple[tuple[str, ...], tuple[str, ...]]
] = [

    # -----------------------------------------------------
    # DEREGISTRATION
    # -----------------------------------------------------
    (
        (
            r"\bşebekeden(?:\s+\w+){0,4}\s+çık\w*",
            r"\bkayıttan(?:\s+\w+){0,4}\s+çık\w*",
            r"\bkayıt(?:\s+\w+){0,3}\s+sil\w*",
            r"\bderegister\w*",
            r"\bderegistration\b",
            r"\bdetach\w*",
        ),
        (
            "UE deregistration procedure",
            "network initiated deregistration",
            "UE initiated deregistration",
        ),
    ),

    # -----------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------
    (
        (
            r"\bşebekeye(?:\s+\w+){0,3}\s+kayıt",
            r"\bkayıt ol\w*",
            r"\bregistration request\b",
            r"\bregister\w*",
            r"\bregistration\b",
        ),
        (
            "5GS registration procedure",
            "Registration Request",
            "Registration Management",
        ),
    ),

    # -----------------------------------------------------
    # CONNECTION / RADIO LOSS
    # -----------------------------------------------------
    #
    # "Şebekeden düşmek" deregistration ile aynı şey
    # kabul edilmez. Radio/RRC tarafına yönlendirilir.
    # -----------------------------------------------------
    (
        (
            r"\bşebekeden(?:\s+\w+){0,4}\s+düş\w*",
            r"\bbağlantı(?:\s+\w+){0,4}\s+kop\w*",
            r"\bsinyal(?:\s+\w+){0,4}\s+git\w*",
            r"\bcoverage loss\b",
            r"\bradio link failure\b",
        ),
        (
            "radio link failure",
            "RRC connection release",
            "loss of coverage",
        ),
    ),

    # -----------------------------------------------------
    # SERVICE REQUEST
    # -----------------------------------------------------
    (
        (
            r"\bservice request\b",
            r"\bservis iste\w*",
            r"\bservis talep\w*",
            r"\bbağlantıyı(?:\s+\w+){0,3}\s+tekrar kur\w*",
            r"\btekrar aktif\w*",
        ),
        (
            "UE triggered Service Request",
            "Service Request procedure",
        ),
    ),

    # -----------------------------------------------------
    # PDU SESSION RELEASE
    # -----------------------------------------------------
    #
    # Release, establishment'tan önce kontrol edilir.
    # Böylece "PDU session nasıl kapatılıyor?"
    # establishment'a gitmez.
    # -----------------------------------------------------
    (
        (
            r"\bpdu session.*\bkapat\w*",
            r"\bpdu session.*\bsonlandır\w*",
            r"\bpdu session.*\brelease\w*",
            r"\boturum.*\bkapat\w*",
            r"\boturum.*\bsonlandır\w*",
            r"\bsession.*\brelease\w*",
        ),
        (
            "PDU Session Release",
            "PDU Session Release procedure",
        ),
    ),

    # -----------------------------------------------------
    # PDU SESSION ESTABLISHMENT
    # -----------------------------------------------------
    (
        (
            r"\bpdu session.*\baç\w*",
            r"\bpdu session.*\bkur\w*",
            r"\bpdu session.*\bestablish\w*",
            r"\boturum aç\w*",
            r"\bdata oturumu.*\baç\w*",
            r"\bveri oturumu.*\baç\w*",
            r"\binternet oturumu.*\baç\w*",
        ),
        (
            "PDU Session Establishment",
            "UE Requested PDU Session Establishment",
        ),
    ),

    # -----------------------------------------------------
    # HANDOVER / MOBILITY
    # -----------------------------------------------------
    (
        (
            r"\bhandover\b",
            r"\bhücre(?:\s+\w+){0,3}\s+değiş\w*",
            r"\bbaz istasyonu(?:\s+\w+){0,3}\s+değiş\w*",
            r"\bcell change\b",
            r"\bmobilite\b",
        ),
        (
            "handover procedure",
            "UE mobility",
            "mobility management",
        ),
    ),

    # -----------------------------------------------------
    # 5G MULTICAST-BROADCAST SERVICES / MBS
    # -----------------------------------------------------
    (
        (
            r"\b5g\b.*\bmulticast\b.*\bbroadcast\b",
            r"\bmulticast[-\s]*broadcast\b",
            r"\bmulticast\b.*\bbroadcast\b",
            r"\b5mbs\b",
            r"\bmbs\b.*\bmimari",
            r"\bmbs\b.*\barchitecture",
        ),
        (
            (
                "architectural enhancements to the 5G system "
                "using NR to support multicast and broadcast "
                "communication services"
            ),
            "5G Multicast-Broadcast Services architecture",
            "Architecture for 5G multicast-broadcast services",
        ),
    ),

    # -----------------------------------------------------
    # CELL BROADCAST / PUBLIC WARNING
    # -----------------------------------------------------
    (
        (
            r"\bcell broadcast\b",
            r"\bhücre yayını\b",
            r"\bacil uyarı\b",
            r"\bwarning message\b",
            r"\buyarı mesaj\w*",
        ),
        (
            "Cell Broadcast",
            "Public Warning System",
            "Cell Broadcast warning message",
        ),
    ),

    # -----------------------------------------------------
    # SMS
    # -----------------------------------------------------
    (
        (
            r"\bsms\b",
            r"\bkısa mesaj\b",
            r"\bmesaj gönder\w*",
            r"\bmesaj ilet\w*",
        ),
        (
            "Short Message Service",
            "SMS procedure",
        ),
    ),

    # -----------------------------------------------------
    # AUTHENTICATION / SECURITY
    # -----------------------------------------------------
    (
        (
            r"\bauthentication\b",
            r"\bkimlik doğrula\w*",
            r"\bdoğrulama\b",
            r"\bauthenticate\w*",
        ),
        (
            "UE authentication",
            "authentication procedure",
            "identification and authentication",
        ),
    ),

    # -----------------------------------------------------
    # NETWORK SELECTION / PLMN
    # -----------------------------------------------------
    (
        (
            r"\bşebeke seç\w*",
            r"\boperatör seç\w*",
            r"\bnetwork selection\b",
            r"\bplmn\b",
        ),
        (
            "PLMN selection",
            "network selection",
        ),
    ),

    # -----------------------------------------------------
    # ROAMING
    # -----------------------------------------------------
    (
        (
            r"\broaming\w*",
            r"\bdolaşım\w*",
            r"\byurt dışında(?:\s+\w+){0,3}\s+şebeke\w*",
        ),
        (
            "roaming procedure",
            "VPLMN HPLMN roaming",
        ),
    ),

    # -----------------------------------------------------
    # EMERGENCY
    # -----------------------------------------------------
    (
        (
            r"\bacil çağrı\w*",
            r"\bemergency call\w*",
            r"\bacil servis\w*",
        ),
        (
            "emergency call",
            "emergency services",
            "emergency registration",
        ),
    ),
]


class QueryNormalizer:
    """
    Kullanıcının doğal dilde yazdığı sorguya,
    standartlarda kullanılan teknik arama
    varyantlarını ekler.

    Önemli:
    - Orijinal sorgu her zaman ilk sıradadır.
    - LLM kullanılmaz.
    - Ağ isteği yapılmaz.
    - Kullanıcının sorusu değiştirilmez.
    - Teknik varyantlar yalnızca retrieval desteğidir.
    """

    def normalize(
        self,
        query: str,
        max_variants: int = 4,
    ) -> list[str]:
        clean_query = self._clean_query(
            query
        )

        if not clean_query:
            raise ValueError(
                "Sorgu boş olamaz."
            )

        if max_variants <= 0:
            raise ValueError(
                "max_variants sıfırdan büyük olmalıdır."
            )

        variants: list[str] = [
            clean_query
        ]

        query_for_matching = (
            clean_query.casefold()
        )

        # -------------------------------------------------
        # KAVRAM EŞLEŞTİRME
        # -------------------------------------------------

        for patterns, expansions in CONCEPT_RULES:
            matched = any(
                re.search(
                    pattern,
                    query_for_matching,
                    flags=re.IGNORECASE,
                )
                is not None
                for pattern in patterns
            )

            if not matched:
                continue

            for expansion in expansions:
                self._append_unique(
                    variants,
                    expansion,
                )

                if (
                    len(variants)
                    >= max_variants
                ):
                    return variants[
                        :max_variants
                    ]

        return variants[
            :max_variants
        ]

    @staticmethod
    def _clean_query(
        query: str,
    ) -> str:
        """
        Gereksiz whitespace'i temizler.

        Kullanıcının kelimelerini veya anlamını
        yeniden yazmaz.
        """

        clean_query = (
            query
            or ""
        ).strip()

        clean_query = re.sub(
            r"\s+",
            " ",
            clean_query,
        )

        return clean_query

    @staticmethod
    def _append_unique(
        variants: list[str],
        value: str,
    ) -> None:
        """
        Aynı teknik query varyantının iki kez
        eklenmesini engeller.
        """

        clean_value = (
            value
            or ""
        ).strip()

        if not clean_value:
            return

        normalized_value = (
            clean_value.casefold()
        )

        existing = {
            item
            .strip()
            .casefold()
            for item in variants
        }

        if normalized_value in existing:
            return

        variants.append(
            clean_value
        )